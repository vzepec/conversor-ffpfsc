"""Ejecución secuencial de la cola de conversión en un hilo de fondo."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator, Sequence
from typing import Protocol

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
)
from ffpfsc_converter.infrastructure.filesystem import remove_quietly
from ffpfsc_converter.infrastructure.mkpfs_adapter import (
    PackProcess,
    build_pack_command,
    parse_progress,
)


class ProcessHandle(Protocol):
    """Contrato mínimo que el runner necesita de un proceso de empaquetado."""

    def lines(self) -> Iterator[str]:
        """Lee la salida del proceso línea a línea hasta que termina.

        Yields:
            str: Cada línea no vacía de la salida.
        """
        ...

    def wait(self) -> int:
        """Espera a que el proceso termine.

        Returns:
            int: Código de salida (``0`` = éxito).
        """
        ...

    def terminate(self) -> None:
        """Termina el proceso si sigue en ejecución."""
        ...


ProcessFactory = Callable[[list[str]], ProcessHandle]


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
        command = build_pack_command(job, options)
        job.state = JobState.RUNNING
        self._emit(JobStarted(job, " ".join(command)))
        started = time.monotonic()
        try:
            process = self._process_factory(command)
        except OSError as exc:
            self._finish(job, ConversionResult(False, False, 0.0, message=str(exc)))
            return
        return_code = self._follow(job, process)
        self._finish(job, self._build_result(job, return_code, time.monotonic() - started))

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
        for line in process.lines():
            progress = parse_progress(line)
            self._emit(JobProgress(job, progress) if progress else LogMessage(line))
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
