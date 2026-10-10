"""Ventana modal de compresión del pipeline: opciones y resumen del reemplazo."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.config import DEFAULT_PRESET, PRESETS
from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions
from ffpfsc_converter.domain.pipeline import PipelineChoice, ReplacePlan
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.ui import presenters
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import Segmented
from ffpfsc_converter.ui.widgets.modal import Modal
from ffpfsc_converter.ui.widgets.stepper import Stepper

_PRESETS_BY_LABEL = {p.label: p for p in PRESETS}


class CompressDialog(Modal):
    """Pide las opciones de compresión y confirma el reemplazo en la PS5."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, job: ConversionJob,
                 plan: ReplacePlan) -> None:
        """Construye la ventana (modal) con los datos del juego descargado.

        Args:
            parent (tk.Misc): Ventana principal.
            theme (ThemeManager): Tema.
            job (ConversionJob): Juego descargado y analizado.
            plan (ReplacePlan): Qué se reemplazará en la PS5.
        """
        subtitle = (f"{presenters.game_info_text(job.info)} · "
                    f"{format_size(job.size)} descargados")
        super().__init__(parent, theme, "Comprimir y reemplazar", subtitle)
        self.result: PipelineChoice | None = None
        self._job = job
        cpu_total = os.cpu_count() or 2
        self._preset = tk.StringVar(value=DEFAULT_PRESET.label)
        self._cores = tk.IntVar(value=cpu_total)
        self._verify = tk.BooleanVar(value=False)
        self._cleanup = tk.BooleanVar(value=True)
        self._build_options(cpu_total)
        self._build_summary(plan)
        self.add_button("Comprimir y reemplazar", self._accept, "Card.Accent.TButton")
        self.add_button("Cancelar", self._cancel)
        self._update_estimate()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.show_modal()

    def ask(self) -> PipelineChoice | None:
        """Muestra la ventana y espera hasta que se cierre.

        Returns:
            PipelineChoice | None: Opciones elegidas, o ``None`` si se canceló.
        """
        self.wait_window()
        return self.result

    def _build_options(self, cpu_total: int) -> None:
        """Crea el modo (con su estimación), los núcleos y los interruptores.

        Args:
            cpu_total (int): Núcleos disponibles.
        """
        m, body = self.theme.metrics, self.body
        modes = [(p.label, p.short_label) for p in PRESETS]
        for caption, widget in (
            ("MODO", Segmented(body, self._preset, modes, self._update_estimate)),
            ("NÚCLEOS", Stepper(body, self.theme, self._cores, (1, cpu_total))),
        ):
            ttk.Label(body, text=caption, style="CardCaption.TLabel").pack(
                anchor="w", pady=(m.px(10), m.px(4)))
            widget.pack(anchor="w")
            if caption == "MODO":
                self._estimate = ttk.Label(body, style="CardMuted.TLabel")
                self._estimate.pack(anchor="w", pady=(m.px(4), 0))
        switch = self.theme.switch_style("surface")
        for text, variable in (("  Verificación completa al final (más lento)", self._verify),
                               ("  Borrar los temporales de este equipo al terminar bien",
                                self._cleanup)):
            ttk.Checkbutton(body, text=text, variable=variable, style=switch).pack(
                anchor="w", pady=(m.px(10), 0))

    def _build_summary(self, plan: ReplacePlan) -> None:
        """Explica qué pasará en la PS5.

        Args:
            plan (ReplacePlan): Qué se reemplazará.
        """
        m = self.theme.metrics
        lines = [f"Se subirá {plan.remote_final} y, una vez verificado, se BORRARÁ de la "
                 f"PS5: {plan.original.path}"]
        if plan.final_exists:
            lines.append(f"Ya existe {plan.remote_final}: se reemplazará.")
        lines.append("Cierra el juego en la PS5 antes de continuar.")
        box = ttk.Frame(self.body, style="Card.Bar.TFrame", padding=(m.px(12), m.px(10)))
        box.pack(fill="x", pady=(m.px(16), 0))
        ttk.Label(box, text="\n".join(lines), style="AltWarn.TLabel", justify="left",
                  wraplength=m.px(480)).pack(anchor="w")

    def _update_estimate(self) -> None:
        """Muestra el peso estimado para el modo elegido."""
        level = _PRESETS_BY_LABEL[self._preset.get()].level
        text = presenters.estimate_text(self._job, level)
        self._estimate.configure(text=f"Peso estimado: {text}")

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
