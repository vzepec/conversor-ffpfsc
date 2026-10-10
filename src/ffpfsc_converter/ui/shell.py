"""Estructura de la ventana: barra lateral con navegación, estado de la PS5 y tema."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from PIL import ImageTk

from ffpfsc_converter.domain.update import ReleaseInfo
from ffpfsc_converter.infrastructure.system import open_url
from ffpfsc_converter.ui.presenters import ConnectionCard, ConsoleStatus, connection_card
from ffpfsc_converter.ui.theme import SIDEBAR_WIDTH, ThemeManager
from ffpfsc_converter.ui.theme.app_icon import render_app_icon
from ffpfsc_converter.ui.widgets.basics import Segmented, StatusDot, icon_button

_THEME_OPTIONS = (("system", "Sistema"), ("light", "Claro"), ("dark", "Oscuro"))


class _NavItem(ttk.Frame):
    """Elemento de la navegación: icono, nombre y contador."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, label: str, icon: str,
                 on_click: Callable[[], None]) -> None:
        """Crea el elemento.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            label (str): Nombre de la vista.
            icon (str): Nombre del icono.
            on_click (Callable[[], None]): Muestra la vista.
        """
        m = theme.metrics
        super().__init__(parent, style="Side.TFrame", padding=(m.px(10), m.px(8)), cursor="hand2")
        self._theme, self._icon = theme, icon
        self._image = ttk.Label(self, style="Side.TLabel")
        self._text = ttk.Label(self, text=label, style="SideMuted.TLabel")
        self._badge = ttk.Label(self, style="Side.PillWait.TLabel")
        self._image.pack(side="left")
        self._text.pack(side="left", padx=(m.px(10), 0))
        for widget in (self, self._image, self._text, self._badge):
            widget.bind("<Button-1>", lambda _e: on_click())
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        """Resalta el elemento de la vista visible.

        Args:
            active (bool): ``True`` si es la vista actual.
        """
        surface = "Sel" if active else "Side"
        self.configure(style="Side.NavOn.TFrame" if active else "Side.TFrame")
        self._badge.configure(style=f"{surface}.PillWait.TLabel")
        self._image.configure(style=f"{surface}.TLabel",
                              image=self._theme.icons.get(self._icon, 18,
                                                          "accent" if active else "muted"))
        self._text.configure(style=f"{surface}{'Bold' if active else 'Muted'}.TLabel")

    def set_badge(self, text: str) -> None:
        """Muestra un contador a la derecha (vacío lo oculta).

        Args:
            text (str): Texto del contador.
        """
        self._badge.configure(text=text)
        if text:
            self._badge.pack(side="right")
        else:
            self._badge.pack_forget()


class AppShell(ttk.Frame):
    """Barra lateral más el área donde se muestra la vista elegida.

    Attributes:
        current (str): Vista visible.
    """

    def __init__(self, root: tk.Misc, theme: ThemeManager, version: str) -> None:
        """Crea la barra lateral y el área de contenido.

        Args:
            root (tk.Misc): Ventana raíz.
            theme (ThemeManager): Tema.
            version (str): Versión de la app (por ejemplo ``"v1.3.1"``).
        """
        super().__init__(root, style="TFrame")
        self._theme = theme
        m = theme.metrics
        self._side = ttk.Frame(self, style="Side.TFrame", width=m.px(SIDEBAR_WIDTH),
                               padding=(m.px(12), m.px(16)))
        self._side.pack(side="left", fill="y")
        self._side.pack_propagate(False)
        self._content = ttk.Frame(self, style="TFrame")
        self._content.pack(side="left", fill="both", expand=True)
        self.current = ""
        self._views: dict[str, ttk.Frame] = {}
        self._items: dict[str, _NavItem] = {}
        self._brand(version)
        self._nav = ttk.Frame(self._side, style="Side.TFrame")
        self._nav.pack(fill="x", pady=(m.px(22), 0))
        self._update: ttk.Button | None = None
        self._theme_selector()
        self._connection_card()

    def add_view(self, key: str, label: str, icon: str) -> ttk.Frame:
        """Agrega una vista y su elemento de navegación.

        Args:
            key (str): Identificador de la vista.
            label (str): Nombre visible.
            icon (str): Icono de la navegación.

        Returns:
            ttk.Frame: Contenedor donde construir la vista.
        """
        frame = ttk.Frame(self._content, style="TFrame")
        self._views[key] = frame
        item = _NavItem(self._nav, self._theme, label, icon, lambda: self.show(key))
        item.pack(fill="x", pady=(0, self._theme.metrics.px(3)))
        self._items[key] = item
        if len(self._views) == 1:
            self.show(key)
        return frame

    def show(self, key: str) -> None:
        """Muestra una vista y resalta su elemento de navegación.

        Args:
            key (str): Identificador de la vista.
        """
        for name, frame in self._views.items():
            frame.pack_forget()
            self._items[name].set_active(name == key)
        self._views[key].pack(fill="both", expand=True)
        self.current = key

    def set_badge(self, key: str, text: str) -> None:
        """Muestra un contador junto al nombre de una vista.

        Args:
            key (str): Identificador de la vista.
            text (str): Contador (vacío lo oculta).
        """
        self._items[key].set_badge(text)

    def show_connection(self, card: ConnectionCard) -> None:
        """Actualiza la tarjeta de estado de la PS5.

        Args:
            card (ConnectionCard): Estado, título y detalle a mostrar.
        """
        self._dot.set_state(card.state, self._theme.palette)
        self._conn_title.configure(text=card.title)
        for label, text in zip(self._conn_lines, (*card.lines, "", ""), strict=False):
            label.configure(text=text)

    def _brand(self, version: str) -> None:
        """Muestra el icono, el nombre y la versión.

        Args:
            version (str): Versión de la app.
        """
        m = self._theme.metrics
        row = ttk.Frame(self._side, style="Side.TFrame")
        row.pack(fill="x")
        self._mark = ImageTk.PhotoImage(render_app_icon(m.px(30)), master=self)
        ttk.Label(row, image=self._mark, style="Side.TLabel").pack(side="left")
        texts = ttk.Frame(row, style="Side.TFrame")
        texts.pack(side="left", padx=(m.px(10), 0))
        ttk.Label(texts, text="Conversor FFPFSC", style="SideBold.TLabel").pack(anchor="w")
        ttk.Label(texts, text=version, style="SideSmall.TLabel").pack(anchor="w")

    def show_update(self, release: ReleaseInfo) -> None:
        """Muestra el botón verde para descargar una versión nueva.

        Args:
            release (ReleaseInfo): Versión disponible (el botón abre su página).
        """
        if self._update is None:
            self._update = icon_button(self._side, self._theme, "", "download",
                                       lambda: None, style="Side.Success.TButton", role="ok")
            self._update.pack(side="bottom", fill="x", pady=(0, self._theme.metrics.px(10)))
        self._update.configure(text=f" Actualizar a v{release.version}",
                               command=lambda: open_url(release.url))

    def _theme_selector(self) -> None:
        """Crea el selector Sistema / Claro / Oscuro al pie de la barra lateral."""
        m = self._theme.metrics
        box = ttk.Frame(self._side, style="Side.TFrame")
        box.pack(side="bottom", fill="x", pady=(m.px(12), 0))
        ttk.Label(box, text="TEMA", style="SideCaption.TLabel").pack(anchor="w", pady=(0, 4))
        self._mode = tk.StringVar(value=self._theme.mode)
        Segmented(box, self._mode, _THEME_OPTIONS, lambda: self._theme.set_mode(self._mode.get()),
                  surface="Side").pack(fill="x")

    def _connection_card(self) -> None:
        """Crea la tarjeta con el estado de la conexión con la PS5."""
        m = self._theme.metrics
        card = ttk.Frame(self._side, style="Side.Card.TFrame", padding=(m.px(12), m.px(11)))
        card.pack(side="bottom", fill="x")
        head = ttk.Frame(card, style="Surface.TFrame")
        head.pack(fill="x")
        self._dot = StatusDot(head, self._theme, "surface")
        self._dot.pack(side="left")
        self._conn_title = ttk.Label(head, text="Sin conexión", style="CardBold.TLabel")
        self._conn_title.pack(side="left", padx=(m.px(8), 0))
        wrap = m.px(SIDEBAR_WIDTH - 52)
        self._conn_lines = [ttk.Label(card, style="CardSmall.TLabel", wraplength=wrap)
                            for _ in range(2)]
        for label in self._conn_lines:
            label.pack(anchor="w", pady=(m.px(3), 0))
        self.show_connection(connection_card(ConsoleStatus(False, "", False, "")))
