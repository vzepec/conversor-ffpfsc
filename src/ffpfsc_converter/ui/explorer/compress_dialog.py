"""Ventana modal de compresión del pipeline: opciones y resumen del reemplazo."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.config import APP_TITLE, DEFAULT_PRESET, PRESETS
from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions
from ffpfsc_converter.domain.pipeline import PipelineChoice, ReplacePlan
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.ui import presenters, theme

_PRESETS_BY_LABEL = {p.label: p for p in PRESETS}


class CompressDialog(tk.Toplevel):
    """Pide las opciones de compresión y confirma el reemplazo en la PS5."""

    def __init__(self, parent: tk.Misc, job: ConversionJob, plan: ReplacePlan) -> None:
        """Construye la ventana (modal) con los datos del juego descargado.

        Args:
            parent (tk.Misc): Ventana principal.
            job (ConversionJob): Juego descargado y analizado.
            plan (ReplacePlan): Qué se reemplazará en la PS5.
        """
        super().__init__(parent)
        self.title(f"{APP_TITLE} — Comprimir y reemplazar")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result: PipelineChoice | None = None
        self._job = job
        cpu_total = os.cpu_count() or 2
        self._preset = tk.StringVar(value=DEFAULT_PRESET.label)
        self._cores = tk.IntVar(value=cpu_total)
        self._verify = tk.BooleanVar(value=False)
        self._cleanup = tk.BooleanVar(value=True)
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        self._build_header(body)
        self._build_options(body, cpu_total)
        self._build_summary(body, plan)
        self._build_buttons(body)
        self._update_estimate()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()

    def ask(self) -> PipelineChoice | None:
        """Muestra la ventana y espera hasta que se cierre.

        Returns:
            PipelineChoice | None: Opciones elegidas, o ``None`` si se canceló.
        """
        self.wait_window()
        return self.result

    def _build_header(self, body: ttk.Frame) -> None:
        """Muestra el nombre y el tamaño del juego.

        Args:
            body (ttk.Frame): Contenedor.
        """
        name = presenters.game_info_text(self._job.info)
        ttk.Label(body, text=name, font=("Sans", 12, "bold")).pack(anchor="w")
        ttk.Label(body, text=f"Tamaño descargado: {format_size(self._job.size)}").pack(
            anchor="w", pady=(2, 10))

    def _build_options(self, body: ttk.Frame, cpu_total: int) -> None:
        """Crea el selector de modo (con su estimación), núcleos y casillas.

        Args:
            body (ttk.Frame): Contenedor.
            cpu_total (int): Núcleos disponibles.
        """
        grid = ttk.Frame(body)
        grid.pack(fill="x")
        ttk.Label(grid, text="Modo:").grid(row=0, column=0, sticky="w")
        combo = ttk.Combobox(grid, textvariable=self._preset, values=list(_PRESETS_BY_LABEL),
                             state="readonly", width=34)
        combo.grid(row=0, column=1, sticky="w", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._update_estimate())
        self._estimate = ttk.Label(grid, text="")
        self._estimate.grid(row=0, column=2, sticky="w", padx=6)
        ttk.Label(grid, text="Núcleos CPU:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(grid, from_=1, to=cpu_total, textvariable=self._cores, width=5).grid(
            row=1, column=1, sticky="w", padx=6, pady=(6, 0))
        ttk.Checkbutton(body, text="Verificación completa al final (más lento)",
                        variable=self._verify).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(body, text="Borrar los archivos temporales de este equipo al terminar bien",
                        variable=self._cleanup).pack(anchor="w")

    def _build_summary(self, body: ttk.Frame, plan: ReplacePlan) -> None:
        """Explica qué pasará en la PS5.

        Args:
            body (ttk.Frame): Contenedor.
            plan (ReplacePlan): Qué se reemplazará.
        """
        lines = [f"Se subirá {plan.remote_final} y, una vez verificado,",
                 f"se BORRARÁ de la PS5: {plan.original.path}"]
        if plan.final_exists:
            lines.append(f"⚠ Ya existe {plan.remote_final}: se reemplazará.")
        lines.append("Cierra el juego en la PS5 antes de continuar.")
        ttk.Label(body, text="\n".join(lines), foreground=theme.WARNING_FG,
                  justify="left").pack(anchor="w", pady=(12, 0))

    def _build_buttons(self, body: ttk.Frame) -> None:
        """Crea los botones Aceptar y Cancelar.

        Args:
            body (ttk.Frame): Contenedor.
        """
        bar = ttk.Frame(body)
        bar.pack(fill="x", pady=(14, 0))
        ttk.Button(bar, text="Cancelar", command=self._cancel).pack(side="right")
        ttk.Button(bar, text="♻ Comprimir y reemplazar", command=self._accept).pack(
            side="right", padx=6)

    def _update_estimate(self) -> None:
        """Muestra el peso estimado para el modo elegido."""
        level = _PRESETS_BY_LABEL[self._preset.get()].level
        self._estimate.configure(text=presenters.estimate_text(self._job, level))

    def _accept(self) -> None:
        """Guarda la elección y cierra la ventana."""
        options = ConversionOptions(
            compression_level=_PRESETS_BY_LABEL[self._preset.get()].level,
            cpu_count=max(1, int(self._cores.get())),
            full_verify=self._verify.get(),
        )
        self.result = PipelineChoice(options, delete_local=self._cleanup.get())
        self.destroy()

    def _cancel(self) -> None:
        """Cierra la ventana sin elegir."""
        self.result = None
        self.destroy()
