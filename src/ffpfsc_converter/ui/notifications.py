"""Avisos del escritorio al terminar tareas largas.

Solo se avisa si la ventana de la app no tiene el foco: si la estás mirando,
el resultado ya se ve en pantalla.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ffpfsc_converter.domain.events import QueueFinished
from ffpfsc_converter.domain.lz4 import Lz4JobState
from ffpfsc_converter.domain.lz4_events import Lz4Finished
from ffpfsc_converter.domain.pipeline_events import PipelineFinished, UploadFinished
from ffpfsc_converter.domain.remote_events import DownloadQueueFinished
from ffpfsc_converter.infrastructure.notify import send_notification
from ffpfsc_converter.ui.explorer.lz4_status_presenters import finish_title, result_status

_ICON = Path(__file__).resolve().parents[3] / "assets" / "icon.png"
#: Envía una notificación: recibe título, texto e icono.
Sender = Callable[[str, str, Path | None], object]


@dataclass(frozen=True)
class Notification:
    """Aviso a mostrar.

    Attributes:
        title (str): Título.
        body (str): Texto.
    """

    title: str
    body: str


def notification_for(event: object) -> Notification | None:
    """Decide si un evento merece un aviso y con qué texto.

    Args:
        event (object): Evento publicado por un servicio.

    Returns:
        Notification | None: El aviso, o ``None`` si no hace falta avisar (por
        ejemplo, si el usuario mismo canceló).
    """
    if isinstance(event, QueueFinished) and not event.cancelled:
        return Notification("Conversión terminada", "La cola de juegos terminó de comprimirse.")
    if isinstance(event, DownloadQueueFinished) and not event.cancelled:
        return Notification("Descargas terminadas", "Las descargas de la PS5 terminaron.")
    if isinstance(event, UploadFinished):
        title = "Subido a la PS5" if event.succeeded else "No se pudo subir a la PS5"
        return Notification(title, _first_line(event.message))
    if isinstance(event, Lz4Finished) and event.status.state is not Lz4JobState.CANCELLED:
        return Notification(finish_title(event.status), result_status(event.status).detail)
    if isinstance(event, PipelineFinished) and not event.result.cancelled:
        title = ("Juego reemplazado en la PS5" if event.result.succeeded
                 else "Comprimir y reemplazar no terminó")
        return Notification(title, _first_line(event.result.message))
    return None


def _first_line(text: str) -> str:
    """Obtiene la primera línea de un mensaje (las notificaciones son cortas).

    Args:
        text (str): Mensaje completo.

    Returns:
        str: Primera línea no vacía.
    """
    return next((line for line in text.splitlines() if line.strip()), "")


class Notifier:
    """Envía los avisos de los eventos cuando la ventana no tiene el foco."""

    def __init__(self, root: tk.Misc, send: Sender = send_notification) -> None:
        """Prepara el notificador.

        Args:
            root (tk.Misc): Ventana principal (para saber si tiene el foco).
            send (Sender): Envía la notificación (los tests usan un doble).
        """
        self._root, self._send = root, send

    def handle(self, event: object) -> None:
        """Avisa del evento si corresponde.

        Args:
            event (object): Evento publicado por un servicio.
        """
        notification = notification_for(event)
        if notification is None or self._root.focus_displayof() is not None:
            return
        self._send(notification.title, notification.body, _ICON if _ICON.is_file() else None)
