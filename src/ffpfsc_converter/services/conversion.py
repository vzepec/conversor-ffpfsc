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
    """Lo que el runner necesita de un proceso de empaquetado."""

    def lines(self) -> Iterator[str]: ...
    def wait(self) -> int: ...
    def terminate(self) -> None: ...


ProcessFactory = Callable[[list[str]], ProcessHandle]


class ConversionRunner:
    """Convierte trabajos uno tras otro y publica eventos de progreso.

    ``process_factory`` permite sustituir MkPFS por un doble en los tests.
    """

    def __init__(self, emit: EventSink, process_factory: ProcessFactory = PackProcess) -> None:
        self._emit = emit
        self._process_factory = process_factory
        self._process: ProcessHandle | None = None
        self._cancel = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def start(self, jobs: Sequence[ConversionJob], options: ConversionOptions) -> threading.Thread:
        """Lanza la conversión de ``jobs`` en un hilo daemon."""
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

    # ------------------------------------------------------------ internos
    def _run_queue(self, jobs: list[ConversionJob], options: ConversionOptions) -> None:
        try:
            for job in jobs:
                if self._cancel.is_set():
                    break
                self._run_job(job, options)
        finally:
            self._running = False
            self._emit(QueueFinished(cancelled=self._cancel.is_set()))

    def _run_job(self, job: ConversionJob, options: ConversionOptions) -> None:
        command = build_pack_command(job, options)
        job.state = JobState.RUNNING
        self._emit(JobStarted(job, " ".join(command)))
        started = time.monotonic()
        try:
            process = self._process_factory(command)
        except OSError as exc:
            self._finish(job, ConversionResult(False, False, 0.0, message=str(exc)))
            return

        self._process = process
        if self._cancel.is_set():  # cancelado mientras arrancaba
            process.terminate()
        for line in process.lines():
            progress = parse_progress(line)
            self._emit(JobProgress(job, progress) if progress else LogMessage(line))
        return_code = process.wait()
        self._process = None

        cancelled = self._cancel.is_set()
        succeeded = return_code == 0 and not cancelled
        if not succeeded:
            remove_quietly(job.output)
        output_size = job.output.stat().st_size if succeeded and job.output.exists() else 0
        self._finish(job, ConversionResult(
            succeeded=succeeded,
            cancelled=cancelled,
            elapsed_seconds=time.monotonic() - started,
            output_size=output_size,
            message=f"código {return_code}",
        ))

    def _finish(self, job: ConversionJob, result: ConversionResult) -> None:
        if result.succeeded:
            job.state = JobState.SUCCEEDED
        elif result.cancelled:
            job.state = JobState.CANCELLED
        else:
            job.state = JobState.FAILED
        self._emit(JobFinished(job, result))
