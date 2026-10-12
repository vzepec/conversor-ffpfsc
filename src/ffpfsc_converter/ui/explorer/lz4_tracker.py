"""Fila de la compresión LZ4 en la PS5 en el panel de transferencias.

Muestra la fase de exfat2ampr, la barra con el porcentaje, la velocidad, el
tiempo restante y los botones Cancelar o Reanudar.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from ffpfsc_converter.domain.lz4 import Lz4Status
from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.explorer.lz4_status_presenters import (
    CANCELLING_TEXT,
    CHECKING_TEXT,
    RESUME_TEXT,
    RESUMING_TEXT,
    ROW_SUBTITLE,
    WAITING_TEXT,
    can_resume,
    cancel_confirmation,
    code_text,
    failed_status,
    queued_text,
    result_status,
    row_progress,
    row_subtitle,
)
from ffpfsc_converter.ui.explorer.presenters import speed_text
from ffpfsc_converter.ui.explorer.transfer_panel import TransferPanel
from ffpfsc_converter.ui.explorer.transfer_row import TransferRow

_CANCEL_TEXT = "Cancelar"


@dataclass(frozen=True)
class Lz4RowActions:
    """Órdenes que se pueden dar desde la fila.

    Attributes:
        cancel (Callable[[], None]): Cancela la conversión en la PS5.
        resume (Callable[[str], None]): Reanuda la conversión en pausa (recibe su carpeta).
    """

    cancel: Callable[[], None]
    resume: Callable[[str], None]


class Lz4Tracker:
    """Refleja el avance de una conversión de exfat2ampr en su fila."""

    def __init__(self, panel: TransferPanel, name: str, actions: Lz4RowActions) -> None:
        """Agrega la fila del juego al panel.

        Args:
            panel (TransferPanel): Panel de transferencias.
            name (str): Nombre del juego.
            actions (Lz4RowActions): Cancelar y reanudar.
        """
        self._panel, self._actions = panel, actions
        self._row_id = uuid.uuid4().hex
        self._dest = ""
        panel.add_row(self._row_id, name, "compress")
        self._row().set_subtitle(ROW_SUBTITLE)
        self._row().set_state("run", CHECKING_TEXT)
        self._show_cancel()

    @property
    def is_active(self) -> bool:
        """Indica si la conversión sigue en curso o en cola.

        Returns:
            bool: ``True`` hasta que se muestra un resultado.
        """
        row = self._panel.row(self._row_id)
        return row is not None and row.is_active

    def started(self, position: int, dest: str) -> None:
        """Marca la conversión como aceptada por exfat2ampr.

        Args:
            position (int): Lugar en la cola (``0`` = empieza ya).
            dest (str): Carpeta que creará exfat2ampr.
        """
        self._dest = dest
        self._row().set_state("wait" if position > 0 else "run", queued_text(position))
        self._panel.refresh()

    def update(self, status: Lz4Status) -> None:
        """Muestra la fase, la barra, la velocidad y el tiempo restante.

        Args:
            status (Lz4Status): Estado leído de exfat2ampr.
        """
        row = self._row()
        self._dest = status.dest or self._dest
        row.set_subtitle(row_subtitle(status))
        if status.waiting:
            row.set_state("wait", WAITING_TEXT, code_text(status.code, status.message)
                          if status.code else "", active=True)
        else:
            row.set_progress(row_progress(status), speed_text(status.speed_bps),
                             format_eta(status.eta_seconds))
        self._panel.refresh()

    def finish(self, status: Lz4Status) -> None:
        """Muestra el resultado y ofrece «Reanudar» si quedó en pausa.

        Args:
            status (Lz4Status): Último estado.
        """
        row = self._row()
        self._dest = status.dest or self._dest
        row.set_subtitle(ROW_SUBTITLE)
        row.set_state(*result_status(status), active=False)
        if can_resume(status):
            row.set_action(RESUME_TEXT, self._resume, "Card.SmallAccent.TButton")
        else:
            row.set_action("", lambda: None, "")
        self._panel.refresh()

    def fail(self, message: str) -> None:
        """Muestra un error que impidió seguir la conversión.

        Args:
            message (str): Motivo (se muestra su primera línea).
        """
        row = self._row()
        row.set_state(*failed_status(message), active=False)
        row.set_action("", lambda: None, "")
        self._panel.refresh()

    def _show_cancel(self) -> None:
        """Muestra el botón Cancelar de la fila."""
        self._row().set_action(_CANCEL_TEXT, self._cancel, "Card.SmallDanger.TButton")

    def _cancel(self) -> None:
        """Pide confirmar (se borra la carpeta en curso) y cancela."""
        if not dialogs.confirm_warning(cancel_confirmation(self._dest)):
            return
        self._row().disable_action(CANCELLING_TEXT)
        self._actions.cancel()

    def _resume(self) -> None:
        """Reanuda la conversión en pausa y vuelve a mostrar Cancelar."""
        self._row().set_state("run", RESUMING_TEXT)
        self._show_cancel()
        self._panel.refresh()
        self._actions.resume(self._dest)

    def _row(self) -> TransferRow:
        """Obtiene la fila de la conversión.

        Returns:
            TransferRow: Fila del juego en el panel.

        Raises:
            KeyError: Si la fila ya no existe.
        """
        row = self._panel.row(self._row_id)
        if row is None:
            raise KeyError(self._row_id)
        return row
