"""Ventana de progreso del pipeline: 3 pasos, porcentaje, tiempo restante y cancelar."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.config import APP_TITLE
from ffpfsc_converter.domain.pipeline import PipelineResult, PipelineStage
from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.ui import theme
from ffpfsc_converter.ui.explorer.presenters import PIPELINE_STEPS, STAGE_NAMES, STEP_OF_STAGE

_PENDING, _CURRENT, _DONE, _FAILED = "○", "▶", "✔", "✖"


class PipelineWindow(tk.Toplevel):
    """Muestra el avance de "comprimir y reemplazar" en 3 pasos: Descarga, Compresión, Reemplazo."""

    def __init__(self, parent: tk.Misc, title: str, on_cancel: Callable[[], None],
                 on_retry: Callable[[], None]) -> None:
        """Construye la ventana.

        Args:
            parent (tk.Misc): Ventana principal.
            title (str): Nombre del elemento que se reemplaza.
            on_cancel (Callable[[], None]): Se llama al pulsar "Cancelar".
            on_retry (Callable[[], None]): Se llama al pulsar "Reintentar" tras un fallo.
        """
        super().__init__(parent)
        self.title(f"{APP_TITLE} — {title}")
        self.transient(parent.winfo_toplevel())
        self.minsize(560, 0)
        self._on_cancel = on_cancel
        self._finished = False
        self._step: int | None = None
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"Comprimir y reemplazar: {title}",
                  font=("Sans", 12, "bold")).pack(anchor="w", pady=(0, 10))
        self._build_steps(body)
        self._substep = ttk.Label(body, text="", foreground=theme.ACCENT_FG)
        self._substep.pack(anchor="w", pady=(12, 4))
        row = ttk.Frame(body)
        row.pack(fill="x")
        self._bar = ttk.Progressbar(row, maximum=100)
        self._bar.pack(side="left", fill="x", expand=True)
        self._percent = ttk.Label(row, text="0 %", width=7, anchor="e",
                                  font=("Sans", 11, "bold"))
        self._percent.pack(side="left", padx=(8, 0))
        self._detail = ttk.Label(body, text="", wraplength=540, justify="left")
        self._detail.pack(anchor="w", pady=(4, 0))
        self._eta = ttk.Label(body, text="", foreground=theme.HINT_FG)
        self._eta.pack(anchor="w")
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(12, 0))
        self._button = ttk.Button(buttons, text="■ Cancelar", command=self._close_or_cancel)
        self._button.pack(side="right")
        self._retry = ttk.Button(buttons, text="↻ Reintentar", command=on_retry)
        self.protocol("WM_DELETE_WINDOW", self._close_or_cancel)

    def _build_steps(self, body: ttk.Frame) -> None:
        """Crea la fila con los 3 pasos.

        Args:
            body (ttk.Frame): Contenedor.
        """
        steps = ttk.Frame(body)
        steps.pack(fill="x")
        self._steps: list[ttk.Label] = []
        for index, name in enumerate(PIPELINE_STEPS):
            if index:
                ttk.Label(steps, text="  →  ", foreground=theme.HINT_FG).pack(side="left")
            label = ttk.Label(steps, text=f"{_PENDING} {index + 1}. {name}",
                              foreground=theme.HINT_FG, font=("Sans", 11))
            label.pack(side="left")
            self._steps.append(label)

    def set_stage(self, stage: PipelineStage, detail: str) -> None:
        """Avanza al paso de la etapa y muestra el subpaso actual.

        Args:
            stage (PipelineStage): Etapa interna nueva.
            detail (str): Texto adicional (ruta afectada, etc.).
        """
        step = STEP_OF_STAGE[stage]
        for index in range(step):
            self._mark(index, _DONE, "")
        self._mark(step, _CURRENT, theme.ACCENT_FG)
        self._step = step
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
            for index in range(len(PIPELINE_STEPS)):
                self._mark(index, _DONE, "")
            self._substep.configure(text="Listo")
            self._show(100.0, result.message, None)
        else:
            if self._step is not None:
                self._mark(self._step, _FAILED, theme.WARNING_FG)
            self._substep.configure(text="Cancelado" if result.cancelled else "Error")
            self._detail.configure(text=result.message)
            self._eta.configure(text="")
            self._retry.pack(side="right", padx=(0, 6))
        self._button.configure(text="Cerrar", state="normal")

    def restart(self) -> None:
        """Vuelve al estado "en curso" para un reintento."""
        self._finished = False
        self._retry.pack_forget()
        self._button.configure(text="■ Cancelar", state="normal")
        self._substep.configure(text="Reintentando…")
        self._eta.configure(text="")

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

    def _mark(self, index: int, icon: str, color: str) -> None:
        """Cambia el icono y el color de un paso.

        Args:
            index (int): Paso (0-2).
            icon (str): Icono nuevo.
            color (str): Color del texto; vacío = color normal.
        """
        self._steps[index].configure(text=f"{icon} {index + 1}. {PIPELINE_STEPS[index]}",
                                     foreground=color)

    def _close_or_cancel(self) -> None:
        """Cierra si terminó; si no, pide cancelar."""
        if self._finished:
            self.destroy()
        else:
            self._button.configure(text="Cancelando…", state="disabled")
            self._on_cancel()
