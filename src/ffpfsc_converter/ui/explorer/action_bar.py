"""Barra de acciones sobre la selección del explorador de la PS5."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.ui.explorer.view_presenters import ActionStates
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import icon_button


class ActionBar(ttk.Frame):
    """Cantidad seleccionada y botones Descargar, Comprimir y reemplazar, Subir y Eliminar."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager,
                 actions: dict[str, Callable[[], None]]) -> None:
        """Crea la barra.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            actions (dict[str, Callable[[], None]]): Acciones ``"download"``, ``"convert"``,
                ``"upload"`` y ``"delete"``.
        """
        m = theme.metrics
        super().__init__(parent, style="Bar.TFrame", padding=(m.px(12), m.px(8)))
        self._count = ttk.Label(self, style="AltBold.TLabel")
        self._count.pack(side="left", padx=(0, m.px(8)))
        self._buttons = {
            "download": icon_button(self, theme, "Descargar", "download", actions["download"],
                                    style="Alt.Small.TButton"),
            "convert": icon_button(self, theme, "Comprimir y reemplazar…", "replace",
                                   actions["convert"], style="Alt.SmallAccent.TButton",
                                   role="accent_ink"),
            "delete": icon_button(self, theme, "Eliminar", "trash", actions["delete"],
                                  style="Alt.SmallDanger.TButton", role="bad"),
            "upload": icon_button(self, theme, "Subir archivo…", "upload", actions["upload"],
                                  style="Alt.SmallGhost.TButton"),
        }
        for key in ("download", "convert"):
            self._buttons[key].pack(side="left", padx=(0, m.px(8)))
        self._buttons["delete"].pack(side="right")
        self._buttons["upload"].pack(side="right", padx=(0, m.px(8)))

    def show(self, text: str, states: ActionStates) -> None:
        """Muestra la cantidad seleccionada y habilita los botones que aplican.

        Args:
            text (str): Por ejemplo ``"1 seleccionado"``.
            states (ActionStates): Botones habilitados.
        """
        self._count.configure(text=text)
        for key, button in self._buttons.items():
            button.state(["!disabled"] if getattr(states, key) else ["disabled"])
