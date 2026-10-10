"""Tarjeta de opciones: modo de compresión, núcleos, verificación y carpeta de destino."""
from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.config import DEFAULT_PRESET, PRESETS
from ffpfsc_converter.domain.models import CompressionPreset
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import Segmented
from ffpfsc_converter.ui.widgets.stepper import Stepper

_PRESETS_BY_LABEL = {p.label: p for p in PRESETS}
_DEFAULT_OUTPUT_TEXT = "Junto a cada juego"


class OptionsPanel(ttk.Frame):
    """Controles con las opciones de conversión elegidas por el usuario.

    Attributes:
        cpu_total (int): Núcleos detectados en el equipo.
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager,
                 on_preset_changed: Callable[[], None],
                 on_change_output: Callable[[], None]) -> None:
        """Crea los controles con los valores predeterminados.

        Args:
            parent (tk.Misc): Contenedor del panel.
            theme (ThemeManager): Tema.
            on_preset_changed (Callable[[], None]): Se llama al cambiar el modo.
            on_change_output (Callable[[], None]): Se llama al pulsar "Cambiar".
        """
        m = self._metrics = theme.metrics
        super().__init__(parent, style="Card.TFrame", padding=(m.px(16), m.px(12)))
        self.cpu_total = os.cpu_count() or 2
        self._preset_var = tk.StringVar(value=DEFAULT_PRESET.label)
        self._cores_var = tk.IntVar(value=self.cpu_total)
        self._verify_var = tk.BooleanVar(value=False)
        self.columnconfigure(2, weight=1)
        modes = [(p.label, p.short_label) for p in PRESETS]
        self._field(0, "MODO", Segmented(self, self._preset_var, modes, on_preset_changed))
        self._field(1, "NÚCLEOS", Stepper(self, theme, self._cores_var, (1, self.cpu_total)))
        verify = ttk.Checkbutton(self, text="  Más lento, más seguro", variable=self._verify_var,
                                 style=theme.switch_style("surface"))
        self._field(2, "VERIFICACIÓN COMPLETA", verify)
        self._build_destination(on_change_output)

    def _build_destination(self, on_change_output: Callable[[], None]) -> None:
        """Crea la línea inferior con la carpeta donde se guardan los ``.ffpfsc``.

        Args:
            on_change_output (Callable[[], None]): Se llama al pulsar "Cambiar".
        """
        m = self._metrics
        ttk.Separator(self).grid(row=2, column=0, columnspan=3, sticky="ew",
                                 pady=(m.px(12), m.px(8)))
        dest = ttk.Frame(self, style="Surface.TFrame")
        dest.grid(row=3, column=0, columnspan=3, sticky="ew")
        ttk.Label(dest, text="GUARDAR EN", style="CardCaption.TLabel").pack(side="left")
        self._outdir_label = ttk.Label(dest, text=_DEFAULT_OUTPUT_TEXT, style="Card.TLabel")
        self._outdir_label.pack(side="left", padx=(m.px(10), 0))
        ttk.Button(dest, text="Cambiar", style="Card.Link.TButton", cursor="hand2",
                   command=on_change_output).pack(side="left", padx=(m.px(6), 0))

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

    def set_output_dir(self, folder: Path) -> None:
        """Muestra la carpeta de destino elegida.

        Args:
            folder (Path): Carpeta donde se guardarán los ``.ffpfsc``.
        """
        self._outdir_label.configure(text=str(folder))
