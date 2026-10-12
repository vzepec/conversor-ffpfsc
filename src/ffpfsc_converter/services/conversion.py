"""Ejecución secuencial de la cola de conversión en un hilo de fondo."""
from __future__ import annotations

import threading
import time
from collections.abc import Sequence

from ffpfsc_converter.config import PROGRESS_INTERVAL_SECONDS
from ffpfsc_converter.domain.events import (
    EventSink,
    JobFinished,
    JobProgress,
    JobStarted,
    LogMessage,
    QueueFinished,
)
from ffpfsc_converter.domain.models import (
    ConversionJob,
    ConversionOptions,
    ConversionResult,
    JobState,
    OutputFormat,
)
from ffpfsc_converter.infrastructure.filesystem import remove_quietly
from ffpfsc_converter.infrastructure.mkpfs_adapter import (
    PackProcess,
    build_pack_command,
    parse_progress,
)
from ffpfsc_converter.services.lz4_local import Lz4LocalConversion
from ffpfsc_converter.services.lz4_local_steps import StepContext
from ffpfsc_converter.services.process_handle import ProcessFactory, ProcessHandle
from ffpfsc_converter.services.skip_switch import SkipSwitch
from ffpfsc_converter.timing import PercentEta

_COMPLETE = 100  # porcentaje con el que MkPFS cierra cada fase




class ConversionRunner:
    """Convierte trabajos uno tras otro y publica eventos de progreso."""

    def __init__(self, emit: EventSink, process_factory: ProcessFactory = PackProcess) -> None:
        """Prepara el runner sin iniciar ninguna conversión.

        Args:
            emit (EventSink): Destino de los eventos (seguro entre hilos).
            process_factory (ProcessFactory): Crea el proceso a partir del comando;
                los tests lo sustituyen por un doble.
        """
        self._emit = emit
        self._process_factory = process_factory
        self._process: ProcessHandle | None = None
        self._cancel = threading.Event()
        self._running = False
        self._skip = SkipSwitch()
        self._lz4 = Lz4LocalConversion(StepContext(emit, process_factory, self._cancel,
                                                   self._set_process, self._skip))

    @property
    def is_running(self) -> bool:
        """Indica si hay una cola en curso.

        Returns:
            bool: ``True`` desde ``start`` hasta que se publica ``QueueFinished``.
        """
        return self._running

    @property
    def cancel_requested(self) -> bool:
        """Indica si el usuario pidió cancelar la cola actual.

        Returns:
            bool: ``True`` tras llamar a ``cancel``.
        """
        return self._cancel.is_set()

    def start(self, jobs: Sequence[ConversionJob], options: ConversionOptions) -> threading.Thread:
        """Lanza la conversión de los trabajos en un hilo daemon.

        Args:
            jobs (Sequence[ConversionJob]): Trabajos a convertir, en orden.
            options (ConversionOptions): Opciones comunes a toda la tanda.

        Returns:
            threading.Thread: Hilo ya iniciado.

        Raises:
            RuntimeError: Si ya hay una conversión en curso.
        """
        if self._running:
            raise RuntimeError("Ya hay una conversión en curso")
        self._running = True
        self._cancel.clear()
        thread = threading.Thread(target=self._run_queue, args=(list(jobs), options), daemon=True)
        thread.start()
        return thread

    def cancel(self) -> None:
        """Pide cancelar: termina el proceso actual y no inicia los siguientes."""
        self._cancel.set()
        process = self._process
        if process is not None:
            process.terminate()

    def skip_verification(self) -> bool:
        """Salta la verificación LZ4 en curso: el juego queda listo sin comprobarlo.

        Returns:
            bool: ``True`` si había una verificación que saltar.
        """
        if not self._skip.request():
            return False
        process = self._process
        if process is not None:
            process.terminate()
        return True

    def _run_queue(self, jobs: list[ConversionJob], options: ConversionOptions) -> None:
        """Convierte los trabajos en orden y publica ``QueueFinished`` al terminar.

        Args:
            jobs (list[ConversionJob]): Trabajos a convertir.
            options (ConversionOptions): Opciones comunes a toda la tanda.
        """
        try:
            for job in jobs:
                if self._cancel.is_set():
                    break
                self._run_job(job, options)
        finally:
            self._running = False
            self._emit(QueueFinished(cancelled=self._cancel.is_set()))

    def _run_job(self, job: ConversionJob, options: ConversionOptions) -> None:
        """Convierte un trabajo y publica su inicio, progreso y resultado.

        Args:
            job (ConversionJob): Trabajo a convertir.
            options (ConversionOptions): Opciones de la conversión.
        """
        job.state = JobState.RUNNING
        if options.output_format is OutputFormat.LZ4:
            self._finish(job, self._lz4.run(job, options))
            return
        command = build_pack_command(job, options)
        self._emit(JobStarted(job, " ".join(command)))
        # MkPFS no sabe sobrescribir: si la salida existe pregunta por consola y, sin
        # consola, falla. La interfaz ya pidió confirmación antes de llegar aquí.
        remove_quietly(job.output)
        started = time.monotonic()
        try:
            process = self._process_factory(command)
        except OSError as exc:
            self._finish(job, ConversionResult(False, False, 0.0, message=str(exc)))
            return
        return_code = self._follow(job, process)
        self._finish(job, self._build_result(job, return_code, time.monotonic() - started))

    def _set_process(self, process: ProcessHandle | None) -> None:
        """Registra el proceso en curso para poder terminarlo al cancelar.

        Args:
            process (ProcessHandle | None): Proceso lanzado, o ``None`` al terminar.
        """
        self._process = process
        if process is not None and self._cancel.is_set():  # cancelado mientras arrancaba
            process.terminate()

    def _follow(self, job: ConversionJob, process: ProcessHandle) -> int:
        """Reenvía la salida del proceso como eventos hasta que termina.

        Args:
            job (ConversionJob): Trabajo en curso.
            process (ProcessHandle): Proceso recién lanzado.

        Returns:
            int: Código de salida del proceso.
        """
        self._process = process
        if self._cancel.is_set():  # cancelado mientras arrancaba
            process.terminate()
        eta = PercentEta()
        last_time, last_phase = 0.0, ""
        for line in process.lines():
            progress = parse_progress(line)
            if progress is None:
                self._emit(LogMessage(line))
                continue
            remaining = eta.update(progress.phase, progress.percent)
            now = time.monotonic()
            # MkPFS redibuja su barra cientos o miles de veces por segundo: publicar
            # cada una saturaría la interfaz. Se publica como máximo una vez por
            # intervalo, además de cada cambio de fase y el final de cada fase.
            if (now - last_time >= PROGRESS_INTERVAL_SECONDS or progress.phase != last_phase
                    or progress.percent >= _COMPLETE):
                self._emit(JobProgress(job, progress, remaining))
                last_time, last_phase = now, progress.phase
        return_code = process.wait()
        self._process = None
        return return_code

    def _build_result(
        self, job: ConversionJob, return_code: int, elapsed: float
    ) -> ConversionResult:
        """Construye el resultado y borra la salida parcial si no hubo éxito.

        Args:
            job (ConversionJob): Trabajo terminado.
            return_code (int): Código de salida de MkPFS.
            elapsed (float): Segundos transcurridos.

        Returns:
            ConversionResult: Resultado con el tamaño final si tuvo éxito.
        """
        cancelled = self._cancel.is_set()
        succeeded = return_code == 0 and not cancelled
        if not succeeded:
            remove_quietly(job.output)
        output_size = job.output.stat().st_size if succeeded and job.output.exists() else 0
        return ConversionResult(
            succeeded=succeeded,
            cancelled=cancelled,
            elapsed_seconds=elapsed,
            output_size=output_size,
            message=f"código {return_code}",
        )

    def _finish(self, job: ConversionJob, result: ConversionResult) -> None:
        """Actualiza el estado del trabajo y publica ``JobFinished``.

        Args:
            job (ConversionJob): Trabajo terminado.
            result (ConversionResult): Resultado de la conversión.
        """
        if result.succeeded:
            job.state = JobState.SUCCEEDED
        elif result.cancelled:
            job.state = JobState.CANCELLED
        else:
            job.state = JobState.FAILED
        self._emit(JobFinished(job, result))
