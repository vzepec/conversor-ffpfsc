"""Ventana de progreso del pipeline: 3 pasos, porcentaje, tiempo restante y cancelar."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.domain.pipeline import PipelineResult, PipelineStage
from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.ui.explorer.presenters import PIPELINE_STEPS, STAGE_NAMES, STEP_OF_STAGE
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.modal import Modal
from ffpfsc_converter.ui.widgets.steps import Steps

_WIDTH = 500


class PipelineWindow(Modal):
    """Muestra el avance de "comprimir y reemplazar" en 3 pasos: Descarga, Compresión, Reemplazo."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, remote_path: str,
                 actions: tuple[Callable[[], None], Callable[[], None]]) -> None:
        """Construye la ventana y la centra sobre la principal.

        Args:
            parent (tk.Misc): Ventana principal.
            theme (ThemeManager): Tema.
            remote_path (str): Carpeta o imagen de la PS5 que se reemplaza.
            actions (tuple[Callable[[], None], Callable[[], None]]): Cancelar y reintentar.
        """
        super().__init__(parent, theme, "Comprimir y reemplazar", remote_path)
        m = theme.metrics
        self._on_cancel, on_retry = actions
        self._finished = False
        self._step: int | None = None
        self._steps = Steps(self.body, theme, PIPELINE_STEPS, _WIDTH)
        self._steps.pack(fill="x")
        row = ttk.Frame(self.body, style="Surface.TFrame")
        row.pack(fill="x", pady=(m.px(16), m.px(8)))
        self._percent = ttk.Label(row, text="0 %", style="CardDisplay.TLabel")
        self._percent.pack(side="left")
        self._substep = ttk.Label(row, style="CardAccent.TLabel")
        self._substep.pack(side="right", anchor="s", pady=(0, m.px(6)))
        self._bar = ttk.Progressbar(self.body, maximum=100, style="Big.Horizontal.TProgressbar")
        self._bar.pack(fill="x")
        meta = ttk.Frame(self.body, style="Surface.TFrame")
        meta.pack(fill="x", pady=(m.px(8), 0))
        self._detail = ttk.Label(meta, style="CardMuted.TLabel", wraplength=m.px(_WIDTH - 140))
        self._detail.pack(side="left")
        self._eta = ttk.Label(meta, style="CardMuted.TLabel")
        self._eta.pack(side="right", anchor="n")
        self._button = self.add_button("Cancelar", self._close_or_cancel,
                                       "Card.Danger.TButton")
        self._retry = self.add_button("Reintentar", on_retry, "Card.Accent.TButton")
        self._retry.pack_forget()
        self.protocol("WM_DELETE_WINDOW", self._close_or_cancel)
        self.center()

    def set_stage(self, stage: PipelineStage, detail: str) -> None:
        """Avanza al paso de la etapa y muestra el subpaso actual.

        Args:
            stage (PipelineStage): Etapa interna nueva.
            detail (str): Texto adicional (ruta afectada, etc.).
        """
        self._step = STEP_OF_STAGE[stage]
        self._mark("now")
        self._substep.configure(text=STAGE_NAMES[stage])
        self._show(0.0, detail, None)

    def set_progress(self, percent: float, detail: str, eta: float | None) -> None:
        """Actualiza la barra, el porcentaje, el detalle y el tiempo restante.

        Args:
            percent (float): Porcentaje del subpaso actual.
            detail (str): Texto de progreso.
            eta (float | None): Segundos restantes estimados.
        """
        self._show(percent, detail, eta)

    def finish(self, result: PipelineResult) -> None:
        """Muestra el resultado y cambia "Cancelar" por "Cerrar".

        Args:
            result (PipelineResult): Resultado del pipeline.
        """
        self._finished = True
        if result.succeeded:
            self._steps.set_states(["done"] * len(PIPELINE_STEPS))
            self._substep.configure(text="Listo", style="CardOk.TLabel")
            self._show(100.0, result.message, None)
        else:
            self._mark("failed")
            self._substep.configure(text="Cancelado" if result.cancelled else "Error",
                                    style="CardWarn.TLabel")
            self._detail.configure(text=result.message)
            self._eta.configure(text="")
            self._retry.pack(side="right", padx=(0, self.theme.metrics.px(8)))
        self._button.configure(text="Cerrar", style="Card.TButton")
        self._button.state(["!disabled"])

    def restart(self) -> None:
        """Vuelve al estado "en curso" para un reintento."""
        self._finished = False
        self._retry.pack_forget()
        self._button.configure(text="Cancelar", style="Card.Danger.TButton")
        self._button.state(["!disabled"])
        self._substep.configure(text="Reintentando…", style="CardAccent.TLabel")
        self._eta.configure(text="")

    def _mark(self, current: str) -> None:
        """Marca los pasos anteriores como hechos y el actual con su estado.

        Args:
            current (str): ``"now"`` o ``"failed"`` para el paso actual.
        """
        step = self._step if self._step is not None else 0
        self._steps.set_states(["done" if i < step else current if i == step else "todo"
                                for i in range(len(PIPELINE_STEPS))])

    def _show(self, percent: float, detail: str, eta: float | None) -> None:
        """Pinta el avance actual.

        Args:
            percent (float): Porcentaje (0-100).
            detail (str): Texto de progreso.
            eta (float | None): Segundos restantes estimados.
        """
        self._bar.configure(value=percent)
        self._percent.configure(text=f"{percent:.0f} %")
        self._detail.configure(text=detail)
        self._eta.configure(text=format_eta(eta))

    def _close_or_cancel(self) -> None:
        """Cierra si terminó; si no, pide cancelar."""
        if self._finished:
            self.destroy()
        else:
            self._button.configure(text="Cancelando…")
            self._button.state(["disabled"])
            self._on_cancel()
