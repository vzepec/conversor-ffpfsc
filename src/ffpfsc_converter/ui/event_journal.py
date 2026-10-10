"""Resume en una línea los eventos que vale la pena guardar en el registro."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ffpfsc_converter.domain.events import JobFinished, QueueFinished
from ffpfsc_converter.domain.pipeline_events import (
    PipelineFinished,
    PipelineStageChanged,
    UploadFinished,
)
from ffpfsc_converter.domain.remote_events import (
    DownloadFinished,
    FtpReady,
    RemoteConnected,
    RemoteDisconnected,
    RemoteError,
    TransferRetrying,
)
from ffpfsc_converter.domain.update import UpdateAvailable


@dataclass(frozen=True)
class JournalEntry:
    """Línea del registro.

    Attributes:
        level (int): Nivel de ``logging`` (``INFO``, ``WARNING``, ``ERROR``).
        text (str): Descripción del evento.
    """

    level: int
    text: str


def journal_line(event: object) -> JournalEntry | None:
    """Describe un evento para el registro.

    Args:
        event (object): Evento publicado por un servicio.

    Returns:
        JournalEntry | None: Nivel y texto, o ``None`` si el evento no se registra
        (por ejemplo, el avance de una transferencia).
    """
    if isinstance(event, RemoteError):
        return JournalEntry(logging.WARNING, f"PS5: {event.message}")
    if isinstance(event, TransferRetrying):
        return JournalEntry(logging.WARNING, f"Reintento {event.attempt}/{event.max_attempts} "
                                             f"({event.row_id}): {event.reason}")
    if isinstance(event, (RemoteConnected, FtpReady)):
        host, port = event.target.host, event.target.port
        return JournalEntry(logging.INFO, f"PS5 {type(event).__name__}: {host}:{port}")
    if isinstance(event, RemoteDisconnected):
        return JournalEntry(logging.INFO, "PS5 desconectada")
    if isinstance(event, DownloadFinished):
        result = event.result
        return _outcome(result.succeeded, f"Descarga {event.job.entry.path}: {result.message}")
    if isinstance(event, UploadFinished):
        return _outcome(event.succeeded, f"Subida {event.upload_id}: {event.message}")
    if isinstance(event, PipelineStageChanged):
        detail = f"Reemplazo: etapa {event.stage.value} {event.detail}"
        return JournalEntry(logging.INFO, detail.rstrip())
    return _result_line(event)


def _result_line(event: object) -> JournalEntry | None:
    """Describe los eventos de fin de reemplazo, de conversión y de versión nueva.

    Args:
        event (object): Evento publicado por un servicio.

    Returns:
        JournalEntry | None: Línea del registro, o ``None`` si no se registra.
    """
    if isinstance(event, PipelineFinished):
        return _outcome(event.result.succeeded, f"Reemplazo terminado: {event.result.message}")
    if isinstance(event, JobFinished):
        return _outcome(event.result.succeeded,
                        f"Conversión {event.job.source}: {event.result.message or 'correcta'}")
    if isinstance(event, QueueFinished):
        return JournalEntry(logging.INFO, f"Cola terminada (cancelada: {event.cancelled})")
    if isinstance(event, UpdateAvailable):
        return JournalEntry(logging.INFO, f"Versión nueva disponible: {event.release.version}")
    return None


def _outcome(succeeded: bool, text: str) -> JournalEntry:
    """Elige el nivel según el resultado.

    Args:
        succeeded (bool): ``True`` si terminó bien.
        text (str): Descripción.

    Returns:
        JournalEntry: ``INFO`` si terminó bien, ``ERROR`` si no, con el texto.
    """
    return JournalEntry(logging.INFO if succeeded else logging.ERROR, text)
