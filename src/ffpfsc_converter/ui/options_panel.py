"""Tarjeta de opciones: modo, núcleos, verificación, rendimiento en la PS5 y destino."""
from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.config import (
    DEFAULT_PRESET,
    PERFORMANCE_THRESHOLD_GAIN,
    PRESETS,
)
from ffpfsc_converter.domain.models import CompressionPreset, ConversionOptions, OutputFormat
from ffpfsc_converter.infrastructure.settings_store import load_settings
from ffpfsc_converter.services.lz4_local_files import lz4_options
from ffpfsc_converter.ui import job_presenters as jp
from ffpfsc_converter.ui.destination_row import DestinationRow
from ffpfsc_converter.ui.preferences import (
    convert_from,
    save_convert,
    save_lz4_verify,
    save_output_format,
)
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import Segmented
from ffpfsc_converter.ui.widgets.flow_frame import FlowFrame
from ffpfsc_converter.ui.widgets.reveal_box import RevealBox
from ffpfsc_converter.ui.widgets.stepper import Stepper

_PRESETS_BY_LABEL = {p.label: p for p in PRESETS}


class OptionsPanel(ttk.Frame):
    """Controles con las opciones de conversión elegidas por el usuario.

    Recuerda entre sesiones el modo, los núcleos, la verificación, el rendimiento
    en la PS5 y la carpeta de destino.

    Attributes:
        cpu_total (int): Núcleos detectados en el equipo.
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager,
                 on_preset_changed: Callable[[], None],
                 on_output_changed: Callable[[Path | None], None]) -> None:
        """Crea los controles con las últimas opciones usadas.

        Args:
            parent (tk.Misc): Contenedor del panel.
            theme (ThemeManager): Tema.
            on_preset_changed (Callable[[], None]): Se llama al cambiar el modo o el
                rendimiento en la PS5 (cambia el peso estimado).
            on_output_changed (Callable[[Path | None], None]): Recibe la carpeta de destino
                nueva (``None`` = junto a cada juego).
        """
        m = self._metrics = theme.metrics
        super().__init__(parent, style="Card.TFrame", padding=(m.px(16), m.px(12)))
        self.cpu_total = os.cpu_count() or 2
        saved = convert_from(load_settings(), _PRESETS_BY_LABEL, self.cpu_total)
        self._preset_var = tk.StringVar(value=saved.preset or DEFAULT_PRESET.label)
        self._cores_var = tk.IntVar(value=saved.cores or self.cpu_total)
        self._verify_var = tk.BooleanVar(value=saved.full_verify)
        self._lz4_verify_var = tk.BooleanVar(value=saved.lz4_verify)
        self._lz4_verify_var.trace_add(
            "write", lambda *_args: save_lz4_verify(self._lz4_verify_var.get()))
        self._performance_var = tk.BooleanVar(value=saved.performance)
        self._format_var = tk.StringVar(value=saved.output_format.value)
        self._format_var.trace_add("write", lambda *_args: self._on_format())
        for variable in (self._preset_var, self._cores_var, self._verify_var,
                         self._performance_var):
            variable.trace_add("write", lambda *_args: self._remember())
        self.columnconfigure(0, weight=1)
        self._build_fields(theme, on_preset_changed)
        ttk.Separator(self).grid(row=1, column=0, sticky="ew", pady=(m.px(12), m.px(8)))
        self._destination = DestinationRow(self, theme, saved.output_dir, on_output_changed)
        self._destination.grid(row=2, column=0, sticky="ew")

    def _build_fields(self, theme: ThemeManager, on_preset_changed: Callable[[], None]) -> None:
        """Crea los campos en una misma línea flexible; el que solo usa ``.ffpfsc`` se oculta.

        «Rendimiento en la PS5» va en una caja que aparece y desaparece con una animación,
        sin dejar de compartir línea con los demás campos. Verificación completa se queda:
        cada formato recuerda su propio valor.

        Args:
            theme (ThemeManager): Tema.
            on_preset_changed (Callable[[], None]): Se llama al cambiar el formato, el modo o
                el rendimiento en la PS5.
        """
        m, switch = self._metrics, theme.switch_style("surface")
        flow = FlowFrame(self, gap=m.px(26), line_gap=m.px(10))
        flow.grid(row=0, column=0, sticky="ew")
        modes = [(p.label, p.short_label) for p in PRESETS]
        self._field(flow, "FORMATO", lambda box: Segmented(
            box, self._format_var, jp.FORMAT_CHOICES, on_preset_changed))
        self._field(flow, "MODO", lambda box: Segmented(box, self._preset_var, modes,
                                                        on_preset_changed))
        self._field(flow, "NÚCLEOS", lambda box: Stepper(box, theme, self._cores_var,
                                                         (1, self.cpu_total)))
        self._verify_check = self._field(
            flow, "VERIFICACIÓN COMPLETA", lambda box: ttk.Checkbutton(
                box, text="  Más lento, más seguro", variable=self._current_verify(),
                style=switch))
        self._performance_box = RevealBox(flow, flow.refresh)
        self._field(flow, "RENDIMIENTO EN LA PS5", lambda box: ttk.Checkbutton(
            box, text="  Carga más rápido", variable=self._performance_var,
            command=on_preset_changed, style=switch), self._performance_box)
        if self.output_format() is OutputFormat.LZ4:
            self._performance_box.hide(animate=False)

    @property
    def output_dir(self) -> Path | None:
        """Carpeta de destino elegida.

        Returns:
            Path | None: Carpeta, o ``None`` para guardar junto a cada juego.
        """
        return self._destination.output_dir

    def _field(self, flow: FlowFrame, caption: str, build: Callable[[tk.Misc], tk.Widget],
               reveal: RevealBox | None = None) -> tk.Widget:
        """Agrega un control con su etiqueta en mayúsculas encima.

        Args:
            flow (FlowFrame): Línea de campos donde va.
            caption (str): Etiqueta del campo.
            build (Callable[[tk.Misc], tk.Widget]): Crea el control dentro del contenedor
                que recibe.
            reveal (RevealBox | None): Caja animada donde va (si se puede ocultar).

        Returns:
            tk.Widget: Control creado.
        """
        box = ttk.Frame(reveal.inner if reveal else flow, style="Surface.TFrame")
        ttk.Label(box, text=caption, style="CardCaption.TLabel").pack(
            anchor="w", pady=(0, self._metrics.px(4)))
        widget = build(box)
        widget.pack(anchor="w", expand=True)  # centrado en el alto de la línea
        if reveal:  # ocupa el alto de la línea para centrar el control como los demás
            box.pack(anchor="nw", fill="y", expand=True)
        flow.add(reveal or box)
        return widget

    def selected_preset(self) -> CompressionPreset:
        """Obtiene el modo de compresión elegido.

        Returns:
            CompressionPreset: Modo seleccionado.
        """
        return _PRESETS_BY_LABEL[self._preset_var.get()]

    def cpu_count(self) -> int:
        """Obtiene la cantidad de núcleos elegida.

        Returns:
            int: Núcleos a usar, como mínimo ``1``.
        """
        try:
            return max(1, int(self._cores_var.get()))
        except (tk.TclError, ValueError):
            return self.cpu_total

    def full_verify(self) -> bool:
        """Indica si se pidió la verificación completa (según el formato elegido).

        Returns:
            bool: ``True`` si el interruptor está activado.
        """
        return self._current_verify().get()

    def _current_verify(self) -> tk.BooleanVar:
        """Elige el valor de verificación del formato actual (cada uno recuerda el suyo).

        Returns:
            tk.BooleanVar: Verificación de LZ4 o de ``.ffpfsc``.
        """
        return self._lz4_verify_var if self.output_format() is OutputFormat.LZ4 \
            else self._verify_var

    def is_performance(self) -> bool:
        """Indica si se pidió priorizar el rendimiento en la PS5.

        Returns:
            bool: ``True`` si el interruptor está activado.
        """
        return self._performance_var.get()

    def conversion_options(self) -> ConversionOptions:
        """Reúne las opciones elegidas para lanzar una conversión.

        Returns:
            ConversionOptions: Formato, nivel, núcleos, verificación y umbral por bloque.
        """
        level, output_format = self.selected_preset().level, self.output_format()
        if output_format is OutputFormat.LZ4:
            return lz4_options(level, self.cpu_count(), self.full_verify())
        return ConversionOptions(
            compression_level=level,
            cpu_count=self.cpu_count(),
            full_verify=self.full_verify(),
            threshold_gain=PERFORMANCE_THRESHOLD_GAIN if self.is_performance() else 0,
        )

    def output_format(self) -> OutputFormat:
        """Obtiene el formato de salida elegido.

        Returns:
            OutputFormat: ``.ffpfsc`` o LZ4.
        """
        return OutputFormat(self._format_var.get())

    def _on_format(self) -> None:
        """Guarda el formato, oculta o muestra «Rendimiento» y cambia la verificación.

        «Rendimiento en la PS5» solo existe en ``.ffpfsc`` (LZ4 no usa el umbral por bloque
        de MkPFS); la verificación pasa a mostrar el valor recordado del formato elegido.
        """
        save_output_format(self.output_format())
        self._verify_check.configure(variable=self._current_verify())
        if self.output_format() is OutputFormat.LZ4:
            self._performance_box.hide()
        else:
            self._performance_box.show()

    def _remember(self) -> None:
        """Guarda las opciones elegidas para la próxima vez."""
        save_convert(self._preset_var.get(), self.cpu_count(), self._verify_var.get(),
                     self.is_performance())
