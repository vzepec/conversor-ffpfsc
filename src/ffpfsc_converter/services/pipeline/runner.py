"""Orquestador del pipeline "comprimir y reemplazar en la PS5" (un hilo de fondo).

Etapas: descargar → analizar → (ventana de compresión) → comprimir → espacio →
subir ``.part`` → verificar → borrar original → renombrar → FTP en solo lectura →
limpiar. Las transferencias se reintentan solas tras un corte; si aun así falla,
:meth:`Ps5ConversionPipeline.retry` retoma sin repetir lo ya hecho (no vuelve a
comprimir ni a borrar el original). Ante cualquier fallo los archivos locales se conservan.
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Iterable
from pathlib import Path

from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.pipeline import (
    PipelineAttempt,
    PipelineChoice,
    PipelineResult,
    ReplacePlan,
)
from ffpfsc_converter.domain.pipeline_events import (
    PipelineConfirmRequired,
    PipelineFinished,
    PipelineOptionsRequired,
)
from ffpfsc_converter.domain.remote import ConsoleTarget, RemoteEntry
from ffpfsc_converter.domain.remote_events import FtpReady
from ffpfsc_converter.errors import ConverterError, DownloadCancelledError
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.infrastructure.ftp import FTP_ERRORS, FtpClient
from ffpfsc_converter.services.console_access import ConsoleAccess
from ffpfsc_converter.services.launch_errors import describe_launch_error
from ffpfsc_converter.services.pipeline import stages
from ffpfsc_converter.services.pipeline.compress import Compressor, compress_job
from ffpfsc_converter.services.pipeline.plan import build_replace_plan
from ffpfsc_converter.services.pipeline.replace import ReplaceContext, replace_on_console
from ffpfsc_converter.services.pipeline.reporter import PipelineReporter
from ffpfsc_converter.services.remote_client import ClientFactory

_RETRY_HINT = "Pulsa «Reintentar» para continuar donde quedó."


class Ps5ConversionPipeline:
    """Descarga, comprime y reemplaza un juego en la PS5.

    Attributes:
        busy (bool): ``True`` mientras corre.
        last (PipelineAttempt | None): Intento pendiente (base del reintento manual);
            ``None`` tras un reemplazo exitoso.
    """

    def __init__(self, emit: EventSink, access: ConsoleAccess,
                 client_factory: ClientFactory = FtpClient,
                 compressor: Compressor = compress_job) -> None:
        """Prepara el pipeline.

        Args:
            emit (EventSink): Destino de los eventos.
            access (ConsoleAccess): Acceso AVA1 a la consola.
            client_factory (ClientFactory): Crea el cliente FTP.
            compressor (Compressor): Comprime un juego (los tests usan un doble).
        """
        self._emit, self._access = emit, access
        self._factory, self._compressor = client_factory, compressor
        self._answers: queue.Queue[object] = queue.Queue()
        self._cancel = threading.Event()
        self._reporter = PipelineReporter(emit)
        self.busy = False
        self.last: PipelineAttempt | None = None

    def start(self, entry: RemoteEntry, target: ConsoleTarget, siblings: Iterable[str],
              work_dir: Path) -> threading.Thread:
        """Lanza un pipeline nuevo en un hilo daemon.

        Args:
            entry (RemoteEntry): Carpeta o imagen de la PS5 a reemplazar.
            target (ConsoleTarget): FTP actual (solo lectura) para descargar.
            siblings (Iterable[str]): Nombres de la carpeta remota del elemento.
            work_dir (Path): Carpeta local de trabajo.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        self.last = PipelineAttempt(entry, tuple(siblings), work_dir)
        return self.retry(target)

    def retry(self, target: ConsoleTarget) -> threading.Thread:
        """Vuelve a ejecutar el intento pendiente, sin repetir lo que ya se hizo.

        Args:
            target (ConsoleTarget): FTP actual (solo lectura).

        Returns:
            threading.Thread: Hilo ya iniciado.

        Raises:
            RuntimeError: Si no hay un intento pendiente.
        """
        if self.last is None:
            raise RuntimeError("No hay un intento pendiente que reintentar")
        self.busy = True
        self._cancel.clear()
        while not self._answers.empty():
            self._answers.get_nowait()
        thread = threading.Thread(target=self._run, args=(self.last, target), daemon=True)
        thread.start()
        return thread

    def answer(self, value: PipelineChoice | bool | None) -> None:
        """Entrega la respuesta a la ventana de compresión o a una confirmación.

        Args:
            value (PipelineChoice | bool | None): Elección, confirmación, o ``None`` = cancelar.
        """
        self._answers.put(value)

    def cancel(self) -> None:
        """Pide cancelar; las etapas largas se detienen y los archivos locales se conservan."""
        self._cancel.set()
        self._answers.put(None)

    def _run(self, attempt: PipelineAttempt, target: ConsoleTarget) -> None:
        """Ejecuta las etapas pendientes y publica ``PipelineFinished``.

        Args:
            attempt (PipelineAttempt): Intento a ejecutar (se actualiza con el avance).
            target (ConsoleTarget): FTP de solo lectura.
        """
        try:
            result = self._execute(attempt, target)
        except DownloadCancelledError:
            result = PipelineResult(False, True, (
                f"Cancelado. Los archivos quedan en {attempt.work_dir}. {_RETRY_HINT}"))
        except (*FTP_ERRORS, ValueError, ConverterError) as exc:
            message = describe_launch_error(exc, target.host, "completar el reemplazo")
            if attempt.original_deleted:
                message += ("\n\nEl original ya se borró en la PS5; el .ffpfsc sigue en "
                            f"{attempt.work_dir}.")
            result = PipelineResult(False, False, f"{message}\n\n{_RETRY_HINT}")
        finally:
            self.busy = False
        self._emit(PipelineFinished(result))

    def _execute(self, attempt: PipelineAttempt, target: ConsoleTarget) -> PipelineResult:
        """Encadena las etapas, saltando las que ya se completaron en un intento anterior.

        Args:
            attempt (PipelineAttempt): Intento a ejecutar.
            target (ConsoleTarget): FTP de solo lectura.

        Returns:
            PipelineResult: Resultado exitoso.

        Raises:
            DownloadCancelledError: Si se cancela.
            ConverterError: Si una etapa falla.
        """
        plan = build_replace_plan(attempt.entry, attempt.siblings)
        if attempt.job is None or not attempt.job.output.is_file():
            self._download_and_compress(attempt, target, plan)
        job, choice = attempt.job, attempt.choice
        assert job is not None and choice is not None
        ctx = ReplaceContext(
            self._access, self._factory, target.host, target.port, plan, job.output,
            attempt.original_size, self._reporter.stage, self._reporter.report, self._confirm,
            self._cancel.is_set, lambda ro: self._emit(FtpReady(ro, started=True)),
            self._reporter.retry, original_deleted=attempt.original_deleted)
        try:
            size = replace_on_console(ctx)
        finally:
            attempt.original_deleted = ctx.original_deleted
        if choice.delete_local:
            stages.cleanup_stage(job, attempt.work_dir, self._reporter)
        self.last = None  # terminado: no queda nada que reintentar
        saved = f"{format_size(attempt.original_size)} → {format_size(size)}"
        return PipelineResult(True, False, f"{plan.remote_final} ({saved})",
                              attempt.original_size, size)

    def _download_and_compress(self, attempt: PipelineAttempt, target: ConsoleTarget,
                               plan: ReplacePlan) -> None:
        """Descarga, pide las opciones y comprime; guarda el avance en el intento.

        Args:
            attempt (PipelineAttempt): Intento a completar.
            target (ConsoleTarget): FTP de solo lectura.
            plan (ReplacePlan): Plan de reemplazo, para la ventana de compresión.

        Raises:
            DownloadCancelledError: Si se cancela o se cierra la ventana sin elegir.
        """
        download = stages.download_stage(self._factory, target, attempt.entry, attempt.work_dir,
                                         self._reporter, self._cancel.is_set)
        attempt.original_size = download.total_bytes
        job = stages.prepare_stage(download.local_path, attempt.work_dir, self._reporter)
        self._emit(PipelineOptionsRequired(job, plan))
        choice = self._answers.get()
        if not isinstance(choice, PipelineChoice):
            raise DownloadCancelledError()
        stages.compress_stage(job, choice, self._compressor, self._reporter, self._cancel.is_set)
        attempt.job, attempt.choice = job, choice

    def _confirm(self, message: str) -> bool:
        """Pide una confirmación a la interfaz y espera la respuesta.

        Args:
            message (str): Pregunta.

        Returns:
            bool: ``True`` si el usuario aceptó.
        """
        self._emit(PipelineConfirmRequired(message))
        return self._answers.get() is True
