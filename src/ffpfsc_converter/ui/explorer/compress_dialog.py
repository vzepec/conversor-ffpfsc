"""Ventana modal de compresión del pipeline: formato, opciones y resumen del reemplazo."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.config import DEFAULT_PRESET, PERFORMANCE_THRESHOLD_GAIN, PRESETS
from ffpfsc_converter.domain.models import ConversionOptions, OutputFormat
from ffpfsc_converter.domain.pipeline import PipelineChoice
from ffpfsc_converter.domain.pipeline_events import PipelineOptionsRequired
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.services.lz4_local_files import lz4_options
from ffpfsc_converter.services.lz4_local_steps import installed_components
from ffpfsc_converter.ui import job_presenters as jp
from ffpfsc_converter.ui import presenters
from ffpfsc_converter.ui.explorer.presenters import replace_summary
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import Segmented
from ffpfsc_converter.ui.widgets.modal import Modal
from ffpfsc_converter.ui.widgets.reveal_box import RevealBox
from ffpfsc_converter.ui.widgets.stepper import Stepper

_PRESETS_BY_LABEL = {p.label: p for p in PRESETS}


class CompressDialog(Modal):
    """Pide el formato y las opciones de compresión, y confirma el reemplazo en la PS5."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager,
                 request: PipelineOptionsRequired) -> None:
        """Construye la ventana (modal) con los datos del juego descargado.

        Args:
            parent (tk.Misc): Ventana principal.
            theme (ThemeManager): Tema.
            request (PipelineOptionsRequired): Juego analizado y planes de reemplazo.
        """
        job = request.job
        subtitle = (f"{presenters.game_info_text(job.info)} · "
                    f"{format_size(job.size)} descargados")
        super().__init__(parent, theme, "Comprimir y reemplazar", subtitle)
        self.result: PipelineChoice | None = None
        self._request = request
        cpu_total = os.cpu_count() or 2
        self._format = tk.StringVar(value=OutputFormat.FFPFSC.value)
        self._preset = tk.StringVar(value=DEFAULT_PRESET.label)
        self._cores = tk.IntVar(value=cpu_total)
        self._verify = tk.BooleanVar(value=False)
        self._performance = tk.BooleanVar(value=False)
        self._cleanup = tk.BooleanVar(value=True)
        if request.lz4_plan is not None:
            self._build_format()
        self._build_options(cpu_total)
        self._build_summary()
        self.add_button("Comprimir y reemplazar", self._accept, "Card.Accent.TButton")
        self.add_button("Cancelar", self._cancel)
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.show_modal()

    def ask(self) -> PipelineChoice | None:
        """Muestra la ventana y espera hasta que se cierre.

        Returns:
            PipelineChoice | None: Opciones elegidas, o ``None`` si se canceló.
        """
        self.wait_window()
        return self.result

    def _caption(self, text: str) -> None:
        """Agrega el título de un campo.

        Args:
            text (str): Título en mayúsculas.
        """
        m = self.theme.metrics
        ttk.Label(self.body, text=text, style="CardCaption.TLabel").pack(
            anchor="w", pady=(m.px(10), m.px(4)))

    def _build_format(self) -> None:
        """Crea el selector de formato; LZ4 queda desactivado si este juego no lo admite."""
        self._caption("FORMATO")
        selector = Segmented(self.body, self._format, jp.FORMAT_CHOICES, self._on_format)
        selector.pack(anchor="w")
        problem = jp.lz4_problem(self._request.job) or (
            "" if installed_components() else jp.LZ4_MISSING_TEXT)
        if not problem:
            return
        for button in selector.winfo_children():
            if str(button.cget("value")) == OutputFormat.LZ4.value:
                button.state(["disabled"])  # type: ignore[attr-defined]
        ttk.Label(self.body, text=problem, style="CardMuted.TLabel").pack(
            anchor="w", pady=(self.theme.metrics.px(4), 0))

    def _build_options(self, cpu_total: int) -> None:
        """Crea el modo (con su estimación), los núcleos y los interruptores.

        Rendimiento y verificación completa solo existen en ``.ffpfsc``: van en cajas
        que se ocultan con una animación al elegir LZ4.

        Args:
            cpu_total (int): Núcleos disponibles.
        """
        modes = [(p.label, p.short_label) for p in PRESETS]
        self._caption("MODO")
        Segmented(self.body, self._preset, modes, self._refresh).pack(anchor="w")
        self._estimate = ttk.Label(self.body, style="CardMuted.TLabel")
        self._estimate.pack(anchor="w", pady=(self.theme.metrics.px(4), 0))
        self._caption("NÚCLEOS")
        Stepper(self.body, self.theme, self._cores, (1, cpu_total)).pack(anchor="w")
        self._ffpfsc_only: list[RevealBox] = []
        for text, variable in (
            ("  Rendimiento en la PS5 (carga más rápido, pesa algo más)", self._performance),
            ("  Verificación completa al final (más lento)", self._verify),
        ):
            box = RevealBox(self.body, lambda: None)
            box.pack(anchor="w")
            self._switch(box.inner, text, variable)
            self._ffpfsc_only.append(box)
        self._switch(self.body, "  Borrar los temporales de este equipo al terminar bien",
                     self._cleanup)

    def _switch(self, parent: tk.Misc, text: str, variable: tk.BooleanVar) -> None:
        """Agrega un interruptor.

        Args:
            parent (tk.Misc): Contenedor.
            text (str): Texto del interruptor.
            variable (tk.BooleanVar): Valor que controla.
        """
        ttk.Checkbutton(parent, text=text, variable=variable,
                        style=self.theme.switch_style("surface"),
                        command=self._refresh).pack(anchor="w", pady=(self.theme.metrics.px(10), 0))

    def _build_summary(self) -> None:
        """Crea el recuadro que explica qué pasará en la PS5."""
        m = self.theme.metrics
        box = ttk.Frame(self.body, style="Card.Bar.TFrame", padding=(m.px(12), m.px(10)))
        box.pack(fill="x", pady=(m.px(16), 0))
        self._summary = ttk.Label(box, style="AltWarn.TLabel", justify="left",
                                  wraplength=m.px(480))
        self._summary.pack(anchor="w")

    def _is_lz4(self) -> bool:
        """Indica si se eligió LZ4.

        Returns:
            bool: ``True`` con LZ4; ``False`` con ``.ffpfsc``.
        """
        return self._format.get() == OutputFormat.LZ4.value

    def _on_format(self) -> None:
        """Oculta (LZ4) o muestra (``.ffpfsc``) sus opciones propias y actualiza los textos."""
        for box in self._ffpfsc_only:
            box.hide() if self._is_lz4() else box.show()
        self._refresh()

    def _refresh(self) -> None:
        """Muestra el peso estimado y el resumen según el formato y las opciones."""
        job, lz4 = self._request.job, self._is_lz4()
        if lz4:
            text = jp.lz4_estimate_text(job)
        else:
            level = _PRESETS_BY_LABEL[self._preset.get()].level
            text = presenters.estimate_text(job, level, self._performance.get())
        self._estimate.configure(text=f"Peso estimado: {text}")
        plan = self._request.lz4_plan if lz4 else self._request.plan
        assert plan is not None
        self._summary.configure(text=replace_summary(plan, lz4))

    def _accept(self) -> None:
        """Guarda la elección y cierra la ventana."""
        level = _PRESETS_BY_LABEL[self._preset.get()].level
        cores = max(1, int(self._cores.get()))
        options = lz4_options(level, cores) if self._is_lz4() else ConversionOptions(
            compression_level=level,
            cpu_count=cores,
            full_verify=self._verify.get(),
            threshold_gain=PERFORMANCE_THRESHOLD_GAIN if self._performance.get() else 0,
        )
        self.result = PipelineChoice(options, delete_local=self._cleanup.get())
        self.destroy()

    def _cancel(self) -> None:
        """Cierra la ventana sin elegir."""
        self.result = None
        self.destroy()
