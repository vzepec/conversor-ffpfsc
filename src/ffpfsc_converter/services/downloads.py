"""Cola de descargas desde la PS5, ejecutada en un hilo de fondo.

Cada descarga usa su propia sesión FTP, independiente de la del explorador,
para que se pueda seguir navegando mientras se descarga.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Sequence

from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.remote import (
    ConsoleTarget,
    DownloadJob,
    DownloadResult,
    DownloadState,
)
from ffpfsc_converter.domain.remote_events import (
    DownloadFinished,
    DownloadQueueFinished,
    DownloadStarted,
)
from ffpfsc_converter.errors import ConverterError, DownloadCancelledError
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.infrastructure.filesystem import free_space
from ffpfsc_converter.infrastructure.ftp import FTP_ERRORS, FtpClient
from ffpfsc_converter.services.download_planner import (
    DownloadPlan,
    bytes_already_local,
    plan_download,
)
from ffpfsc_converter.services.file_download import LocalWriteError, download_file
from ffpfsc_converter.services.progress_meter import ProgressMeter
from ffpfsc_converter.services.remote_client import ClientFactory, RemoteClient
from ffpfsc_converter.services.remote_errors import describe_error


class NotEnoughSpaceError(ConverterError):
    """No hay espacio en este equipo para completar la descarga."""

    def __init__(self, needed: int, free: int) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            needed (int): Bytes que faltan por descargar.
            free (int): Bytes libres en la carpeta de destino.
        """
        super().__init__(
            f"No hay espacio suficiente en este equipo: faltan {format_size(needed)} "
            f"y hay {format_size(free)} libres."
        )


class DownloadRunner:
    """Descarga trabajos uno tras otro y publica su progreso."""

    def __init__(self, emit: EventSink, client_factory: ClientFactory = FtpClient) -> None:
        """Prepara la cola sin iniciar ninguna descarga.

        Args:
            emit (EventSink): Destino de los eventos (seguro entre hilos).
            client_factory (ClientFactory): Crea el cliente remoto para una consola.
        """
        self._emit = emit
        self._factory = client_factory
        self._cancel = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        """Indica si hay descargas en curso.

        Returns:
            bool: ``True`` desde ``start`` hasta que se publica ``DownloadQueueFinished``.
        """
        return self._running

    def start(self, jobs: Sequence[DownloadJob], target: ConsoleTarget) -> threading.Thread:
        """Lanza las descargas en un hilo daemon.

        Args:
            jobs (Sequence[DownloadJob]): Descargas en orden.
            target (ConsoleTarget): Consola de origen.

        Returns:
            threading.Thread: Hilo ya iniciado.

        Raises:
            RuntimeError: Si ya hay descargas en curso.
        """
        if self._running:
            raise RuntimeError("Ya hay descargas en curso")
        self._running = True
        self._cancel.clear()
        thread = threading.Thread(target=self._run_queue, args=(list(jobs), target), daemon=True)
        thread.start()
        return thread

    def cancel(self) -> None:
        """Pide cancelar: corta la descarga actual y no inicia las siguientes."""
        self._cancel.set()

    def _run_queue(self, jobs: list[DownloadJob], target: ConsoleTarget) -> None:
        """Descarga los trabajos en orden y publica ``DownloadQueueFinished``.

        Args:
            jobs (list[DownloadJob]): Descargas pendientes.
            target (ConsoleTarget): Consola de origen.
        """
        try:
            for job in jobs:
                if self._cancel.is_set():
                    break
                self._run_job(job, target)
        finally:
            self._running = False
            self._emit(DownloadQueueFinished(cancelled=self._cancel.is_set()))

    def _run_job(self, job: DownloadJob, target: ConsoleTarget) -> None:
        """Descarga un trabajo y publica su inicio y su resultado.

        Args:
            job (DownloadJob): Descarga a realizar.
            target (ConsoleTarget): Consola de origen.
        """
        job.state = DownloadState.RUNNING
        self._emit(DownloadStarted(job))
        started = time.monotonic()
        client = self._factory(target)
        try:
            client.connect()
            files = self._transfer(client, job)
            result = DownloadResult(True, False, time.monotonic() - started, files=files)
        except DownloadCancelledError:
            result = DownloadResult(False, True, time.monotonic() - started)
        except ConverterError as exc:
            result = DownloadResult(False, False, time.monotonic() - started, message=str(exc))
        except FTP_ERRORS as exc:
            message = describe_error(exc, target, f"descargar {job.entry.name}")
            result = DownloadResult(False, False, time.monotonic() - started, message=message)
        finally:
            client.close()
        job.state = (DownloadState.SUCCEEDED if result.succeeded else
                     DownloadState.CANCELLED if result.cancelled else DownloadState.FAILED)
        self._emit(DownloadFinished(job, result))

    def _transfer(self, client: RemoteClient, job: DownloadJob) -> int:
        """Planifica y descarga todos los archivos de un trabajo.

        Args:
            client (RemoteClient): Cliente conectado.
            job (DownloadJob): Descarga en curso.

        Returns:
            int: Cantidad de archivos descargados u omitidos por estar completos.

        Raises:
            DownloadCancelledError: Si se canceló.
            NotEnoughSpaceError: Si no cabe en el disco local.
            LocalWriteError: Si no se pudo crear una carpeta local.
        """
        plan = plan_download(client, job.entry, job.destination)
        job.total_bytes, job.done_bytes = plan.total_bytes, 0
        _check_space(plan, job)
        for directory in plan.directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise LocalWriteError(directory, exc) from exc
        meter = ProgressMeter(job, self._emit)
        for transfer in plan.files:
            if self._cancel.is_set():
                raise DownloadCancelledError()
            download_file(client, transfer, meter, self._cancel.is_set)
        meter.publish(job.entry.name)
        return len(plan.files)


def _check_space(plan: DownloadPlan, job: DownloadJob) -> None:
    """Comprueba que lo que falta por descargar cabe en el disco local.

    Args:
        plan (DownloadPlan): Plan de descarga.
        job (DownloadJob): Descarga en curso (define la carpeta de destino).

    Raises:
        NotEnoughSpaceError: Si el espacio libre no alcanza.
        LocalWriteError: Si no se pudo crear o consultar la carpeta de destino.
    """
    needed = plan.total_bytes - bytes_already_local(plan)
    try:
        job.destination.mkdir(parents=True, exist_ok=True)
        free = free_space(job.destination)
    except OSError as exc:
        raise LocalWriteError(job.destination, exc) from exc
    if needed > free:
        raise NotEnoughSpaceError(needed, free)
