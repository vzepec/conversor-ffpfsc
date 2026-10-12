"""Línea «Guardar en» de la vista Convertir: carpeta de destino y cómo cambiarla."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.theme import ThemeManager

_DEFAULT_OUTPUT_TEXT = "Junto a cada juego"


class DestinationRow(ttk.Frame):
    """Muestra la carpeta de destino con los enlaces «Cambiar» y «Usar junto a cada juego».

    Attributes:
        output_dir (Path | None): Carpeta de destino; ``None`` = junto a cada juego.
    """

    def __init__(self, parent: ttk.Frame, theme: ThemeManager, output_dir: Path | None,
                 on_change: Callable[[Path | None], None]) -> None:
        """Crea la línea con la carpeta recordada.

        Args:
            parent (ttk.Frame): Contenedor.
            theme (ThemeManager): Tema.
            output_dir (Path | None): Carpeta inicial; ``None`` = junto a cada juego.
            on_change (Callable[[Path | None], None]): Recibe la carpeta nueva.
        """
        super().__init__(parent, style="Surface.TFrame")
        m = self._metrics = theme.metrics
        self.output_dir = output_dir
        self._on_change = on_change
        ttk.Label(self, text="GUARDAR EN", style="CardCaption.TLabel").pack(side="left")
        self._label = ttk.Label(self, style="Card.TLabel")
        self._label.pack(side="left", padx=(m.px(10), 0))
        ttk.Button(self, text="Cambiar", style="Card.Link.TButton", cursor="hand2",
                   command=self._pick).pack(side="left", padx=(m.px(6), 0))
        self._reset = ttk.Button(self, text=f"Usar «{_DEFAULT_OUTPUT_TEXT.lower()}»",
                                 style="Card.Link.TButton", cursor="hand2",
                                 command=lambda: self._set(None))
        self._show()

    def _pick(self) -> None:
        """Pide la carpeta de destino."""
        folder = dialogs.ask_output_dir()
        if folder:
            self._set(folder)

    def _set(self, folder: Path | None) -> None:
        """Cambia la carpeta de destino y avisa.

        Args:
            folder (Path | None): Carpeta elegida, o ``None`` para guardar junto a cada juego.
        """
        self.output_dir = folder
        self._show()
        self._on_change(folder)

    def _show(self) -> None:
        """Muestra la carpeta de destino y el enlace para volver a la predeterminada."""
        self._label.configure(text=str(self.output_dir or _DEFAULT_OUTPUT_TEXT))
        if self.output_dir is None:
            self._reset.pack_forget()
        else:
            self._reset.pack(side="left", padx=(self._metrics.px(12), 0))
