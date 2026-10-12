"""Ventana que explica que falta ``exfat2ampr.elf`` y ofrece elegirlo o descargarlo."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.config import E2A_RELEASES_URL
from ffpfsc_converter.infrastructure.system import open_url
from ffpfsc_converter.ui.explorer.lz4_presenters import ELF_REQUIRED_TEXT
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.modal import Modal

_TEXT_WIDTH = 460


class ElfRequiredDialog(Modal):
    """Pregunta si se elige ahora el ``exfat2ampr.elf`` (con el enlace de descarga)."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Construye la ventana modal.

        Args:
            parent (tk.Misc): Ventana principal.
            theme (ThemeManager): Tema.
        """
        super().__init__(parent, theme, "Falta exfat2ampr.elf")
        m = theme.metrics
        self.result = False
        ttk.Label(self.body, text=ELF_REQUIRED_TEXT, style="Card.TLabel", justify="left",
                  wraplength=m.px(_TEXT_WIDTH)).pack(anchor="w")
        ttk.Button(self.body, text=E2A_RELEASES_URL, style="Card.Link.TButton", cursor="hand2",
                   command=lambda: open_url(E2A_RELEASES_URL)).pack(anchor="w",
                                                                    pady=(m.px(10), 0))
        self.add_button("Elegir exfat2ampr.elf…", self._accept, "Card.Accent.TButton")
        self.add_button("Cancelar", self.destroy)
        self.show_modal()

    def ask(self) -> bool:
        """Muestra la ventana y espera la respuesta.

        Returns:
            bool: ``True`` si el usuario quiere elegir el archivo ahora.
        """
        self.wait_window()
        return self.result

    def _accept(self) -> None:
        """Acepta y cierra."""
        self.result = True
        self.destroy()
