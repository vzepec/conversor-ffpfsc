"""Fila de «comprimir y reemplazar» en el panel de transferencias.

Muestra el paso (Descarga, Compresión, Reemplazo), la barra con el porcentaje
de la etapa, el tiempo restante y los botones Cancelar o Reintentar, sin abrir
ventanas aparte.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from ffpfsc_converter.domain.pipeline import PipelineResult, PipelineStage
from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.ui.explorer.transfer_panel import TransferPanel
from ffpfsc_converter.ui.explorer.transfer_presenters import (
    pipeline_progress,
    pipeline_result_status,
    pipeline_step_text,
)
from ffpfsc_converter.ui.explorer.transfer_row import TransferRow
from ffpfsc_converter.ui.presenters import SKIP_VERIFY_TEXT


@dataclass(frozen=True)
class PipelineRowActions:
    """Botones de la fila del pipeline.

    Attributes:
        cancel (Callable[[], None]): Cancelar.
        retry (Callable[[], None]): Reintentar tras un fallo.
        skip_verify (Callable[[], None]): Saltar la verificación LZ4 en curso.
    """

    cancel: Callable[[], None]
    retry: Callable[[], None]
    skip_verify: Callable[[], None]


class PipelineTracker:
    """Refleja el avance de un "comprimir y reemplazar" en su fila."""

    def __init__(self, panel: TransferPanel, name: str, actions: PipelineRowActions) -> None:
        """Agrega la fila del juego al panel.

        Args:
            panel (TransferPanel): Panel de transferencias.
            name (str): Nombre de la carpeta o imagen que se reemplaza.
            actions (PipelineRowActions): Cancelar, reintentar y saltar la verificación.
        """
        self._panel = panel
        self._on_cancel, self._on_retry = actions.cancel, actions.retry
        self._on_skip = actions.skip_verify
        self._can_skip = False
        self._row_id = uuid.uuid4().hex
        panel.add_row(self._row_id, name, "replace")
        self._row().set_subtitle("Comprimir y reemplazar")
        self._row().set_state("run", "Preparando…")
        self._show_cancel()

    def set_stage(self, stage: PipelineStage, detail: str) -> None:
        """Muestra el paso nuevo y reinicia la barra.

        Args:
            stage (PipelineStage): Etapa interna nueva.
            detail (str): Texto adicional (ruta afectada, etc.).
        """
        self._row().set_subtitle(pipeline_step_text(stage))
        self.set_progress(0.0, detail, None)

    def set_progress(self, percent: float, detail: str, eta: float | None) -> None:
        """Actualiza la barra, el detalle y el tiempo restante.

        Args:
            percent (float): Porcentaje de la etapa.
            detail (str): Bytes, velocidad o fase de MkPFS.
            eta (float | None): Segundos restantes estimados.
        """
        self._row().set_progress(pipeline_progress(percent, detail), "", format_eta(eta))
        self._panel.refresh()

    def set_skippable(self, can_skip: bool) -> None:
        """Muestra «Saltar verificación» solo mientras se verifica un LZ4.

        Args:
            can_skip (bool): ``True`` durante la verificación LZ4.
        """
        if can_skip == self._can_skip:
            return
        self._can_skip = can_skip
        self._row().set_secondary(SKIP_VERIFY_TEXT if can_skip else "", self._skip)

    def _skip(self) -> None:
        """Pide saltar la verificación y oculta el botón."""
        self.set_skippable(False)
        self._on_skip()

    def finish(self, result: PipelineResult) -> None:
        """Muestra el resultado y ofrece reintentar si no terminó bien.

        Args:
            result (PipelineResult): Resultado del pipeline.
        """
        self.set_skippable(False)
        row = self._row()
        row.set_state(*pipeline_result_status(result), active=False)
        if result.succeeded:
            row.set_subtitle("Comprimir y reemplazar · completado")
            row.set_action("", lambda: None, "")
        else:
            row.set_action("Reintentar", self._on_retry, "Card.SmallAccent.TButton")
        self._panel.refresh()

    def restart(self) -> None:
        """Vuelve al estado "en curso" para un reintento."""
        self._row().set_state("run", "Reintentando…")
        self._show_cancel()
        self._panel.refresh()

    def _show_cancel(self) -> None:
        """Muestra el botón Cancelar de la fila."""
        self._row().set_action("Cancelar", self._cancel, "Card.SmallDanger.TButton")

    def _cancel(self) -> None:
        """Pide cancelar y deja el botón deshabilitado hasta que el pipeline se detenga."""
        self._row().disable_action("Cancelando…")
        self._on_cancel()

    def _row(self) -> TransferRow:
        """Obtiene la fila del pipeline.

        Returns:
            TransferRow: Fila del juego en el panel.

        Raises:
            KeyError: Si la fila ya no existe.
        """
        row = self._panel.row(self._row_id)
        if row is None:
            raise KeyError(self._row_id)
        return row
