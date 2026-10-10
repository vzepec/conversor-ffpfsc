"""Compresión de un juego dentro del pipeline, reutilizando ``ConversionRunner``."""
from __future__ import annotations

import dataclasses
from collections import deque
from collections.abc import Callable

from ffpfsc_converter.domain.events import Event, JobFinished, JobProgress, LogMessage
from ffpfsc_converter.domain.models import (
    ConversionJob,
    ConversionOptions,
    ConversionResult,
    ProgressUpdate,
)
from ffpfsc_converter.services.conversion import ConversionRunner

_POLL_SECONDS = 0.25
_LOG_TAIL = 3

#: Recibe el avance de MkPFS y los segundos restantes estimados de la fase.
CompressProgress = Callable[[ProgressUpdate, float | None], None]
#: Comprime un trabajo: ``(trabajo, opciones, al_avanzar, debe_cancelar) -> resultado``.
Compressor = Callable[
    [ConversionJob, ConversionOptions, CompressProgress, Callable[[], bool]],
    ConversionResult,
]


def compress_job(
    job: ConversionJob,
    options: ConversionOptions,
    on_progress: CompressProgress,
    should_cancel: Callable[[], bool],
) -> ConversionResult:
    """Comprime un juego con MkPFS y espera el resultado (bloqueante).

    Args:
        job (ConversionJob): Juego descargado y analizado.
        options (ConversionOptions): Nivel, núcleos y verificación.
        on_progress (CompressProgress): Recibe el progreso de MkPFS y su ETA.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Returns:
        ConversionResult: Resultado; si falla, el mensaje incluye las últimas
        líneas del registro de MkPFS.
    """
    results: list[ConversionResult] = []
    tail: deque[str] = deque(maxlen=_LOG_TAIL)

    def sink(event: Event) -> None:
        """Recoge el progreso, el registro y el resultado del runner.

        Args:
            event (Event): Evento publicado por ``ConversionRunner``.
        """
        if isinstance(event, JobProgress):
            on_progress(event.progress, event.eta_seconds)
        elif isinstance(event, LogMessage):
            tail.append(event.text)
        elif isinstance(event, JobFinished):
            results.append(event.result)

    runner = ConversionRunner(sink)
    thread = runner.start([job], options)
    while thread.is_alive():
        thread.join(_POLL_SECONDS)
        if should_cancel() and not runner.cancel_requested:
            runner.cancel()
    if not results:
        return ConversionResult(False, should_cancel(), 0.0, message="MkPFS no informó resultado")
    result = results[0]
    if not result.succeeded and not result.cancelled and tail:
        result = dataclasses.replace(result, message=f"{result.message}: {' | '.join(tail)}")
    return result
