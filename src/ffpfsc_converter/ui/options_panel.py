"""Panel de opciones: modo de compresión, núcleos, destino y verificación."""
from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.config import DEFAULT_PRESET, PRESETS
from ffpfsc_converter.domain.models import CompressionPreset

_PRESETS_BY_LABEL = {p.label: p for p in PRESETS}
_DEFAULT_OUTPUT_TEXT = "Misma carpeta que el juego"


class OptionsPanel(ttk.Frame):
    """Controles con las opciones de conversión elegidas por el usuario."""

    def __init__(
        self,
        parent: tk.Misc,
        on_preset_changed: Callable[[], None],
        on_change_output: Callable[[], None],
    ) -> None:
        """Crea los controles con los valores predeterminados.

        Args:
            parent (tk.Misc): Contenedor del panel.
            on_preset_changed (Callable[[], None]): Se llama al cambiar el modo.
            on_change_output (Callable[[], None]): Se llama al pulsar "Cambiar…".
        """
        super().__init__(parent)
        self.cpu_total = os.cpu_count() or 2
        self._preset_var = tk.StringVar(value=DEFAULT_PRESET.label)
        self._cores_var = tk.IntVar(value=self.cpu_total)
        self._verify_var = tk.BooleanVar(value=False)
        self._build_first_row(on_preset_changed)
        self._build_output_rows(on_change_output)

    def _build_first_row(self, on_preset_changed: Callable[[], None]) -> None:
        """Crea el selector de modo y el selector de núcleos.

        Args:
            on_preset_changed (Callable[[], None]): Se llama al cambiar el modo.
        """
        ttk.Label(self, text="Modo:").grid(row=0, column=0, sticky="w")
        combo = ttk.Combobox(self, textvariable=self._preset_var, values=list(_PRESETS_BY_LABEL),
                             state="readonly", width=34)
        combo.grid(row=0, column=1, sticky="w", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _e: on_preset_changed())
        ttk.Label(self, text="Núcleos CPU:").grid(row=0, column=2, sticky="e", padx=(16, 0))
        ttk.Spinbox(self, from_=1, to=self.cpu_total, textvariable=self._cores_var,
                    width=5).grid(row=0, column=3, sticky="w", padx=6)
        ttk.Label(self, text=f"(detectados: {self.cpu_total})").grid(row=0, column=4, sticky="w")

    def _build_output_rows(self, on_change_output: Callable[[], None]) -> None:
        """Crea la fila de carpeta de destino y la casilla de verificación.

        Args:
            on_change_output (Callable[[], None]): Se llama al pulsar "Cambiar…".
        """
        ttk.Label(self, text="Guardar en:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._outdir_label = ttk.Label(self, text=_DEFAULT_OUTPUT_TEXT, width=48)
        self._outdir_label.grid(row=1, column=1, columnspan=2, sticky="w", padx=6, pady=(6, 0))
        ttk.Button(self, text="Cambiar…", command=on_change_output).grid(
            row=1, column=3, sticky="w", padx=6, pady=(6, 0))
        ttk.Checkbutton(self, text="Verificación completa al final (más lento)",
                        variable=self._verify_var).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))

    def selected_preset(self) -> CompressionPreset:
        """Obtiene el modo de compresión elegido.

        Returns:
            CompressionPreset: Modo seleccionado en el desplegable.
        """
        return _PRESETS_BY_LABEL[self._preset_var.get()]

    def cpu_count(self) -> int:
        """Obtiene la cantidad de núcleos elegida.

        Returns:
            int: Núcleos a usar, como mínimo ``1``.
        """
        return max(1, int(self._cores_var.get()))

    def full_verify(self) -> bool:
        """Indica si se pidió la verificación completa.

        Returns:
            bool: ``True`` si la casilla está marcada.
        """
        return self._verify_var.get()

    def set_output_dir(self, folder: Path) -> None:
        """Muestra la carpeta de destino elegida.

        Args:
            folder (Path): Carpeta donde se guardarán los ``.ffpfsc``.
        """
        self._outdir_label.configure(text=str(folder))
