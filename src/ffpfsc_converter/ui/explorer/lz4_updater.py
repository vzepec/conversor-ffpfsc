"""Aplica en la vista PS5 los eventos de la compresión LZ4 remota (exfat2ampr)."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ffpfsc_converter.domain.lz4_events import (
    Lz4ElfRequired,
    Lz4EngineLaunched,
    Lz4Failed,
    Lz4Finished,
    Lz4PairingRequired,
    Lz4Progress,
    Lz4Ready,
    Lz4Rejected,
    Lz4Started,
)
from ffpfsc_converter.ui.explorer.lz4_presenters import ENGINE_LAUNCHED_TEXT
from ffpfsc_converter.ui.explorer.lz4_status_presenters import job_name

if TYPE_CHECKING:  # evita la importación circular con el controlador
    from ffpfsc_converter.ui.explorer.controller import ExplorerController


class Lz4Updater:
    """Manejadores de los eventos de exfat2ampr.

    Attributes:
        handlers (dict[type, Callable]): Tipo de evento → manejador.
    """

    def __init__(self, controller: ExplorerController) -> None:
        """Registra los manejadores.

        Args:
            controller (ExplorerController): Controlador de la vista PS5.
        """
        self._lz4 = controller.lz4
        self.handlers: dict[type, Callable] = {
            Lz4EngineLaunched: lambda _e: self._lz4.show_status(ENGINE_LAUNCHED_TEXT),
            Lz4ElfRequired: lambda e: self._lz4.ask_elf(e.host, e.entry_path),
            Lz4PairingRequired: self._lz4.ask_pairing,
            Lz4Ready: lambda e: self._lz4.review(e.host, e.plan),
            Lz4Rejected: lambda e: self._lz4.rejected(e.check),
            Lz4Started: self._on_started,
            Lz4Progress: lambda e: self._lz4.row_for(e.host, job_name(e.status)).update(e.status),
            Lz4Finished: lambda e: self._lz4.finished(e.host, e.status),
            Lz4Failed: lambda e: self._lz4.failed(e.message),
        }

    def _on_started(self, event: Lz4Started) -> None:
        """Marca la fila como aceptada por exfat2ampr (en curso o en cola).

        Args:
            event (Lz4Started): Conversión aceptada.
        """
        source = event.request.source
        tracker = self._lz4.row_for(event.host, source.title or source.title_id)
        tracker.started(event.position, event.request.output_path)

