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
from ffpfsc_converter.infrastructure.ftp import FTP_ERRORS, FtpClient
from ffpfsc_converter.services.remote_client import ClientFactory
from ffpfsc_converter.services.remote_download import download_with_retries
from ffpfsc_converter.services.remote_errors import describe_error


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
        try:
            files = download_with_retries(self._factory, target, job, self._emit,
                                          self._cancel.is_set)
            result = DownloadResult(True, False, time.monotonic() - started, files=files)
        except DownloadCancelledError:
            result = DownloadResult(False, True, time.monotonic() - started)
        except ConverterError as exc:
            result = DownloadResult(False, False, time.monotonic() - started, message=str(exc))
        except FTP_ERRORS as exc:
            message = describe_error(exc, target, f"descargar {job.entry.name}")
            result = DownloadResult(False, False, time.monotonic() - started, message=message)
        job.state = (DownloadState.SUCCEEDED if result.succeeded else
                     DownloadState.CANCELLED if result.cancelled else DownloadState.FAILED)
        self._emit(DownloadFinished(job, result))
