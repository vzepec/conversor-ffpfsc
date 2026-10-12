"""Ventana para escribir el código de emparejamiento que muestra la PS5."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.modal import Modal

_CODE_WIDTH = 10
_TEXT_WIDTH = 440
_DEFAULT_MESSAGE = ("La PS5 muestra una notificación con un código de 6 dígitos.\n"
                    "Escríbelo aquí (tienes menos de un minuto):")


class PairingDialog(Modal):
    """Pide el código de 6 dígitos para vincular la app con la consola."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, console_name: str,
                 message: str | None = None) -> None:
        """Construye la ventana modal.

        Args:
            parent (tk.Misc): Ventana principal.
            theme (ThemeManager): Tema.
            console_name (str): Nombre de la consola (o del programa), para el título.
            message (str | None): Instrucciones propias; ``None`` usa las del FTP, cuyo
                código caduca en un minuto.
        """
        super().__init__(parent, theme, f"Emparejar con {console_name}")
        m = theme.metrics
        self.result: str | None = None
        self._code = tk.StringVar()
        ttk.Label(self.body, text=message or _DEFAULT_MESSAGE, style="Card.TLabel",
                  justify="left", wraplength=m.px(_TEXT_WIDTH)).pack(anchor="w")
        entry = ttk.Entry(self.body, textvariable=self._code, width=_CODE_WIDTH,
                          style="Card.TEntry", font=theme.fonts.title, justify="center")
        entry.pack(anchor="w", pady=(m.px(14), 0))
        entry.bind("<Return>", lambda _e: self._accept())
        entry.focus_set()
        self.add_button("Emparejar", self._accept, "Card.Accent.TButton")
        self.add_button("Cancelar", self.destroy)
        self.show_modal()

    def ask(self) -> str | None:
        """Muestra la ventana y espera el código.

        Returns:
            str | None: Código escrito, o ``None`` si se canceló.
        """
        self.wait_window()
        return self.result

    def _accept(self) -> None:
        """Guarda el código y cierra."""
        self.result = self._code.get().strip()
        self.destroy()
