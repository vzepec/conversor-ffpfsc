"""Barra de acciones sobre la selección del explorador de la PS5."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.ui.explorer.view_presenters import ActionStates
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import icon_button

#: Botón → (texto completo, texto corto para ventanas angostas).
_LABELS = {"upload": ("Subir a la PS5…", "Subir…")}
#: Opciones del menú «Subir a la PS5…» → acción.
_UPLOAD_MENU = (("Archivos…", "upload"), ("Carpeta…", "upload_folder"))


class ActionBar(ttk.Frame):
    """Cantidad seleccionada y botones Descargar, Comprimir y reemplazar, Subir y Eliminar."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager,
                 actions: dict[str, Callable[[], None]]) -> None:
        """Crea la barra.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            actions (dict[str, Callable[[], None]]): Acciones ``"download"``, ``"convert"``,
                ``"upload"`` (archivos), ``"upload_folder"`` y ``"delete"``.
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
            "upload": icon_button(self, theme, _LABELS["upload"][0], "upload",
                                  self._show_upload_menu, style="Alt.SmallGhost.TButton"),
        }
        self._upload_menu = tk.Menu(self, tearoff=False)
        for label, key in _UPLOAD_MENU:
            self._upload_menu.add_command(label=label, command=actions[key])
        self._paint_menu(theme)
        theme.on_change(lambda _p: self._paint_menu(theme))
        for key in ("download", "convert"):
            self._buttons[key].pack(side="left", padx=(0, m.px(8)))
        self._buttons["delete"].pack(side="right")
        self._buttons["upload"].pack(side="right", padx=(0, m.px(8)))
        self._full_width = 0
        self.bind("<Configure>", lambda _e: self._fit_labels(), add="+")

    def show(self, text: str, states: ActionStates) -> None:
        """Muestra la cantidad seleccionada y habilita los botones que aplican.

        Args:
            text (str): Por ejemplo ``"1 seleccionado"``.
            states (ActionStates): Botones habilitados.
        """
        self._count.configure(text=text)
        for key, button in self._buttons.items():
            button.state(["!disabled"] if getattr(states, key) else ["disabled"])

    def _show_upload_menu(self) -> None:
        """Despliega «Archivos…» y «Carpeta…» bajo el botón «Subir a la PS5…»."""
        button = self._buttons["upload"]
        self._upload_menu.tk_popup(button.winfo_rootx(),
                                   button.winfo_rooty() + button.winfo_height())

    def _paint_menu(self, theme: ThemeManager) -> None:
        """Aplica los colores del tema al menú (no es un widget ttk).

        Args:
            theme (ThemeManager): Tema actual.
        """
        p = theme.palette
        self._upload_menu.configure(background=p.surface, foreground=p.text,
                                    activeborderwidth=0, activebackground=p.accent_soft,
                                    activeforeground=p.text, relief="flat", bd=1,
                                    font=theme.fonts.body)

    def _fit_labels(self) -> None:
        """Acorta los textos de algunos botones si la barra no alcanza para todos."""
        if not self._full_width:  # el primer cálculo se hace con los textos completos
            self._full_width = self.winfo_reqwidth()
        compact = self.winfo_width() < self._full_width
        for key, (full, short) in _LABELS.items():
            # ``width=0`` quita el ancho mínimo del tema para que el texto corto ahorre espacio.
            self._buttons[key].configure(text=f" {short if compact else full}", width=0)
