"""Barra de ruta: subir de carpeta, ruta con tramos clicables, accesos rápidos y actualizar.

Un clic en el espacio libre de la ruta la convierte en un campo para escribirla.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk

from ffpfsc_converter.ui.explorer.view_presenters import path_crumbs
from ffpfsc_converter.ui.theme import Palette, ThemeManager
from ffpfsc_converter.ui.widgets.basics import icon_button


class PathBar(ttk.Frame):
    """Navegación por las carpetas de la PS5."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, favorites: Sequence[str],
                 actions: tuple[Callable[[], None], Callable[[str], None], Callable[[], None]],
                 ) -> None:
        """Crea la barra.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            favorites (Sequence[str]): Rutas del menú «Accesos rápidos».
            actions (tuple[Callable[[], None], Callable[[str], None], Callable[[], None]]):
                Subir de carpeta, ir a una ruta y actualizar.
        """
        super().__init__(parent, style="TFrame")
        self._theme, m = theme, theme.metrics
        on_up, self._on_go_to, on_refresh = actions
        self._path = "/"
        self._up = icon_button(self, theme, "Subir", "arrow_up", on_up, style="Small.TButton")
        self._up.pack(side="left")
        self._refresh = icon_button(self, theme, "Actualizar", "refresh", on_refresh,
                                    style="Small.TButton")
        self._refresh.pack(side="right")
        self._quick = ttk.Button(self, text="Accesos rápidos ▾", style="Small.TButton",
                                 command=self._show_menu, takefocus=False)
        self._quick.pack(side="right", padx=(0, m.px(8)))
        self._box = ttk.Frame(self, style="Path.TFrame", padding=(m.px(10), m.px(5)))
        self._box.pack(side="left", fill="x", expand=True, padx=m.px(8))
        self._box.bind("<Button-1>", lambda _e: self._edit())
        self._entry = tk.Entry(self._box, relief="flat", bd=0, highlightthickness=0,
                               font=theme.fonts.mono)
        self._entry.bind("<Return>", lambda _e: self._submit())
        self._entry.bind("<Escape>", lambda _e: self._show_crumbs())
        self._entry.bind("<FocusOut>", lambda _e: self._show_crumbs())
        self._menu = tk.Menu(self, tearoff=False)
        for path in favorites:
            self._menu.add_command(label=path, command=lambda p=path: self._on_go_to(p))
        self._paint(theme.palette)
        theme.on_change(self._paint)
        self._connected, self._enabled = False, False
        self.set_path("/")

    def set_path(self, path: str) -> None:
        """Muestra la carpeta abierta como tramos clicables.

        Args:
            path (str): Ruta absoluta.
        """
        self._path = path
        self._show_crumbs()

    def set_connected(self, connected: bool) -> None:
        """Muestra la ruta si hay conexión, o el aviso para conectar.

        Args:
            connected (bool): ``True`` si hay sesión con la PS5.
        """
        self._connected = connected
        self.set_enabled(connected)

    def set_enabled(self, enabled: bool) -> None:
        """Habilita o pausa la navegación (la ruta se sigue viendo).

        Args:
            enabled (bool): ``True`` para permitir navegar.
        """
        self._enabled = enabled and self._connected
        for button in (self._up, self._refresh, self._quick):
            button.state(["!disabled"] if self._enabled else ["disabled"])
        self._show_crumbs()

    def _show_crumbs(self) -> None:
        """Dibuja la ruta como «/ data / homebrew» con cada tramo clicable."""
        self._entry.pack_forget()
        for child in self._box.winfo_children():
            if child is not self._entry:
                child.destroy()
        if not self._connected:
            ttk.Label(self._box, text="Conecta la PS5 para explorar sus carpetas",
                      style="CardMuted.TLabel").pack(side="left")
            return
        self._crumb("/", "/", muted=True)
        for index, (name, path) in enumerate(path_crumbs(self._path)):
            if index:
                self._crumb("/", "", muted=True)
            self._crumb(name, path)

    def _crumb(self, text: str, path: str, muted: bool = False) -> None:
        """Agrega un tramo de la ruta.

        Args:
            text (str): Texto del tramo.
            path (str): Ruta a la que lleva al hacer clic (vacía = separador sin acción).
            muted (bool): ``True`` para los separadores.
        """
        label = ttk.Label(self._box, text=text,
                          style="CardMonoMuted.TLabel" if muted else "CardMono.TLabel")
        label.pack(side="left", padx=(0, self._theme.metrics.px(4)))
        if path and self._enabled:
            label.configure(cursor="hand2")
            label.bind("<Button-1>", lambda _e: self._on_go_to(path))

    def _edit(self) -> None:
        """Cambia la ruta por un campo de texto para escribir otra."""
        if not self._enabled:
            return
        for child in self._box.winfo_children():
            if child is not self._entry:
                child.destroy()
        self._entry.delete(0, "end")
        self._entry.insert(0, self._path)
        self._entry.pack(side="left", fill="x", expand=True)
        self._entry.focus_set()
        self._entry.select_range(0, "end")

    def _submit(self) -> None:
        """Abre la ruta escrita."""
        path = self._entry.get()
        self._show_crumbs()
        self._on_go_to(path)

    def _show_menu(self) -> None:
        """Despliega los accesos rápidos bajo su botón."""
        x = self._quick.winfo_rootx()
        y = self._quick.winfo_rooty() + self._quick.winfo_height()
        self._menu.tk_popup(x, y)

    def _paint(self, p: Palette) -> None:
        """Aplica los colores del tema al campo y al menú (no son widgets ttk).

        Args:
            p (Palette): Paleta actual.
        """
        self._entry.configure(background=p.surface, foreground=p.text, insertbackground=p.text,
                              selectbackground=p.accent_soft, selectforeground=p.text)
        self._menu.configure(background=p.surface, foreground=p.text, activeborderwidth=0,
                             activebackground=p.accent_soft, activeforeground=p.text,
                             relief="flat", bd=1, font=self._theme.fonts.mono)
