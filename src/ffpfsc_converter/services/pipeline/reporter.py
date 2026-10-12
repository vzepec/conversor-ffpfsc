"""Publica las etapas y el progreso del pipeline como eventos."""
from __future__ import annotations

import time
from collections.abc import Callable

from ffpfsc_converter.config import LZ4_VERIFY_PHASE, PROGRESS_INTERVAL_SECONDS
from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.models import ProgressUpdate
from ffpfsc_converter.domain.pipeline import PipelineStage
from ffpfsc_converter.domain.pipeline_events import PipelineProgress, PipelineStageChanged
from ffpfsc_converter.domain.remote_events import DownloadProgress, TransferRetrying
from ffpfsc_converter.formatting import PHASE_NAMES, format_size


class PipelineReporter:
    """Recuerda la etapa actual y traduce cada tipo de avance a ``PipelineProgress``."""

    def __init__(self, emit: EventSink, clock: Callable[[], float] = time.monotonic) -> None:
        """Prepara el publicador.

        Args:
            emit (EventSink): Destino de los eventos.
            clock (Callable[[], float]): Reloj monotónico; los tests usan un doble.
        """
        self._emit, self._clock = emit, clock
        self.current = PipelineStage.DOWNLOAD
        self._percent = 0.0
        self._last_report = float("-inf")

    def stage(self, stage: PipelineStage, detail: str) -> None:
        """Publica el cambio de etapa.

        Args:
            stage (PipelineStage): Etapa nueva.
            detail (str): Texto adicional.
        """
        self.current, self._percent = stage, 0.0
        self._last_report = float("-inf")
        self._emit(PipelineStageChanged(stage, detail))

    def report(self, done: int, total: int, speed: float, eta: float | None = None) -> None:
        """Publica el avance de la etapa actual (bytes, o elementos al borrar).

        Se publica como máximo una vez por ``PROGRESS_INTERVAL_SECONDS`` (y siempre al
        llegar al final): algunas etapas, como el CRC32, avisan cientos de veces por
        segundo y saturarían la interfaz.

        Args:
            done (int): Cantidad completada.
            total (int): Cantidad total.
            speed (float): Bytes por segundo (0 si no aplica).
            eta (float | None): Segundos restantes estimados, si se conocen.
        """
        percent = done * 100 / total if total else 0.0
        self._percent = percent
        now = self._clock()
        if now - self._last_report < PROGRESS_INTERVAL_SECONDS and done < total:
            return
        self._last_report = now
        if self.current is PipelineStage.DELETE_ORIGINAL:
            detail = f"{done} de {total} elementos"
        else:
            detail = f"{format_size(done)} de {format_size(total)}"
            detail += f"  —  {format_size(speed)}/s" if speed else ""
        self._emit(PipelineProgress(self.current, percent, detail, eta))

    def on_download(self, event: object) -> None:
        """Traduce el progreso de la descarga.

        Args:
            event (object): Evento publicado por ``transfer_job``.
        """
        if isinstance(event, DownloadProgress):
            self.report(event.job.done_bytes, event.job.total_bytes, event.bytes_per_second,
                        event.eta_seconds)
        elif isinstance(event, TransferRetrying):
            self._announce_retry(event.attempt, event.max_attempts, event.reason)

    def retry(self, attempt: int, max_attempts: int, exc: BaseException) -> None:
        """Anuncia un reintento automático de la subida (``RetryCallback``).

        Args:
            attempt (int): Reintento que comienza.
            max_attempts (int): Reintentos máximos.
            exc (BaseException): Error que lo provocó.
        """
        self._announce_retry(attempt, max_attempts, "Se perdió la conexión con la PS5")

    def _announce_retry(self, attempt: int, max_attempts: int, reason: str) -> None:
        """Muestra el aviso de reintento conservando el porcentaje alcanzado.

        Args:
            attempt (int): Reintento que comienza.
            max_attempts (int): Reintentos máximos.
            reason (str): Causa del corte.
        """
        detail = f"⚠ {reason}. Reintentando ({attempt} de {max_attempts})…"
        self._emit(PipelineProgress(self.current, self._percent, detail, None))

    def on_compress(self, progress: ProgressUpdate, eta: float | None) -> None:
        """Traduce el progreso de MkPFS.

        Args:
            progress (ProgressUpdate): Avance de MkPFS.
            eta (float | None): Segundos restantes estimados de la fase.
        """
        detail = PHASE_NAMES.get(progress.phase, progress.phase)
        detail += f"  —  {progress.speed}" if progress.speed else ""
        self._emit(PipelineProgress(PipelineStage.COMPRESS, float(progress.percent), detail, eta,
                                    can_skip=progress.phase == LZ4_VERIFY_PHASE))
