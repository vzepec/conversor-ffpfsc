"""Tarjeta de opciones: modo, núcleos, verificación, rendimiento en la PS5 y destino."""
from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.config import DEFAULT_PRESET, PERFORMANCE_THRESHOLD_GAIN, PRESETS
from ffpfsc_converter.domain.models import CompressionPreset, ConversionOptions
from ffpfsc_converter.infrastructure.settings_store import load_settings
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.preferences import convert_from, save_convert
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import Segmented
from ffpfsc_converter.ui.widgets.stepper import Stepper

_PRESETS_BY_LABEL = {p.label: p for p in PRESETS}
_DEFAULT_OUTPUT_TEXT = "Junto a cada juego"


class OptionsPanel(ttk.Frame):
    """Controles con las opciones de conversión elegidas por el usuario.

    Recuerda entre sesiones el modo, los núcleos, la verificación, el rendimiento
    en la PS5 y la carpeta de destino.

    Attributes:
        cpu_total (int): Núcleos detectados en el equipo.
        output_dir (Path | None): Carpeta de destino; ``None`` = junto a cada juego.
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
        self.output_dir = saved.output_dir
        self._on_output_changed = on_output_changed
        self._preset_var = tk.StringVar(value=saved.preset or DEFAULT_PRESET.label)
        self._cores_var = tk.IntVar(value=saved.cores or self.cpu_total)
        self._verify_var = tk.BooleanVar(value=saved.full_verify)
        self._performance_var = tk.BooleanVar(value=saved.performance)
        for variable in (self._preset_var, self._cores_var, self._verify_var,
                         self._performance_var):
            variable.trace_add("write", lambda *_args: self._remember())
        self.columnconfigure(2, weight=1)
        modes = [(p.label, p.short_label) for p in PRESETS]
        self._field(0, "MODO", Segmented(self, self._preset_var, modes, on_preset_changed))
        self._field(1, "NÚCLEOS", Stepper(self, theme, self._cores_var, (1, self.cpu_total)))
        verify = ttk.Checkbutton(self, text="  Más lento, más seguro", variable=self._verify_var,
                                 style=theme.switch_style("surface"))
        self._field(2, "VERIFICACIÓN COMPLETA", verify)
        self._build_destination(theme, on_preset_changed)

    def _build_destination(self, theme: ThemeManager,
                           on_performance_changed: Callable[[], None]) -> None:
        """Crea la línea inferior: carpeta de los ``.ffpfsc`` y rendimiento en la PS5.

        Args:
            theme (ThemeManager): Tema.
            on_performance_changed (Callable[[], None]): Se llama al cambiar el interruptor.
        """
        m = self._metrics
        ttk.Separator(self).grid(row=2, column=0, columnspan=3, sticky="ew",
                                 pady=(m.px(12), m.px(8)))
        dest = ttk.Frame(self, style="Surface.TFrame")
        dest.grid(row=3, column=0, columnspan=3, sticky="ew")
        # Se ubica primero a la derecha para que una ruta de destino larga no lo tape.
        ttk.Checkbutton(dest, text="  Carga más rápido, pesa algo más",
                        variable=self._performance_var, command=on_performance_changed,
                        style=theme.switch_style("surface")).pack(side="right")
        ttk.Label(dest, text="RENDIMIENTO EN LA PS5", style="CardCaption.TLabel").pack(
            side="right", padx=(m.px(16), m.px(10)))
        ttk.Label(dest, text="GUARDAR EN", style="CardCaption.TLabel").pack(side="left")
        self._outdir_label = ttk.Label(dest, style="Card.TLabel")
        self._outdir_label.pack(side="left", padx=(m.px(10), 0))
        ttk.Button(dest, text="Cambiar", style="Card.Link.TButton", cursor="hand2",
                   command=self._pick_output).pack(side="left", padx=(m.px(6), 0))
        self._reset = ttk.Button(dest, text=f"Usar «{_DEFAULT_OUTPUT_TEXT.lower()}»",
                                 style="Card.Link.TButton", cursor="hand2",
                                 command=lambda: self._set_output(None))
        self._show_output()

    def _field(self, column: int, caption: str, widget: tk.Widget) -> None:
        """Ubica un control con su etiqueta en mayúsculas encima.

        Args:
            column (int): Columna de la cuadrícula.
            caption (str): Etiqueta del campo.
            widget (tk.Widget): Control.
        """
        pad = (0, self._metrics.px(26))
        ttk.Label(self, text=caption, style="CardCaption.TLabel").grid(
            row=0, column=column, sticky="w", padx=pad, pady=(0, self._metrics.px(4)))
        widget.grid(row=1, column=column, sticky="w", padx=pad)

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
        """Indica si se pidió la verificación completa.

        Returns:
            bool: ``True`` si el interruptor está activado.
        """
        return self._verify_var.get()

    def is_performance(self) -> bool:
        """Indica si se pidió priorizar el rendimiento en la PS5.

        Returns:
            bool: ``True`` si el interruptor está activado.
        """
        return self._performance_var.get()

    def conversion_options(self) -> ConversionOptions:
        """Reúne las opciones elegidas para lanzar una conversión.

        Returns:
            ConversionOptions: Nivel, núcleos, verificación y umbral de ganancia por bloque.
        """
        return ConversionOptions(
            compression_level=self.selected_preset().level,
            cpu_count=self.cpu_count(),
            full_verify=self.full_verify(),
            threshold_gain=PERFORMANCE_THRESHOLD_GAIN if self.is_performance() else 0,
        )

    def _pick_output(self) -> None:
        """Pide la carpeta de destino."""
        folder = dialogs.ask_output_dir()
        if folder:
            self._set_output(folder)

    def _set_output(self, folder: Path | None) -> None:
        """Cambia la carpeta de destino y avisa al controlador.

        Args:
            folder (Path | None): Carpeta elegida, o ``None`` para guardar junto a cada juego.
        """
        self.output_dir = folder
        self._show_output()
        self._on_output_changed(folder)

    def _show_output(self) -> None:
        """Muestra la carpeta de destino y el enlace para volver a la predeterminada."""
        self._outdir_label.configure(text=str(self.output_dir or _DEFAULT_OUTPUT_TEXT))
        if self.output_dir is None:
            self._reset.pack_forget()
        else:
            self._reset.pack(side="left", padx=(self._metrics.px(12), 0))

    def _remember(self) -> None:
        """Guarda las opciones elegidas para la próxima vez."""
        save_convert(self._preset_var.get(), self.cpu_count(), self.full_verify(),
                     self.is_performance())
