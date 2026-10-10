"""Creación de la ventana principal: escala, identidad en el sistema, tema, tamaño e icono."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

from PIL import ImageTk

from ffpfsc_converter.config import WINDOW_CLASS, WINDOWS_APP_ID
from ffpfsc_converter.infrastructure.settings_store import load_settings
from ffpfsc_converter.infrastructure.system import enable_dpi_awareness, set_windows_app_id
from ffpfsc_converter.ui import presenters, theme
from ffpfsc_converter.ui.dnd import create_root
from ffpfsc_converter.ui.preferences import WindowPreferences, save_window, window_from
from ffpfsc_converter.ui.theme.app_icon import set_window_icon

#: Vistas de la ventana, en el orden de la barra lateral.
VIEWS = ("convert", "ps5")
_ZOOMED = "zoomed"


@dataclass
class Window:
    """Ventana raíz lista para construir las vistas.

    Attributes:
        root (tk.Tk): Ventana raíz.
        theme (theme.ThemeManager): Tema aplicado.
        icons (list[ImageTk.PhotoImage]): Imágenes del icono (se conservan mientras viva).
        saved (WindowPreferences): Tamaño y vista de la sesión anterior.
    """

    root: tk.Tk
    theme: theme.ThemeManager
    icons: list[ImageTk.PhotoImage]
    saved: WindowPreferences


def create_window() -> Window:
    """Crea la ventana con su título, tema, icono y el tamaño de la última sesión.

    Returns:
        Window: Ventana y tema listos.
    """
    enable_dpi_awareness()
    set_windows_app_id(WINDOWS_APP_ID)
    root = create_root(WINDOW_CLASS)
    root.title(presenters.window_title())
    manager = theme.ThemeManager(root)
    px = manager.metrics.px
    minimum = (px(theme.WINDOW_MIN_SIZE[0]), px(theme.WINDOW_MIN_SIZE[1]))
    screen = (root.winfo_screenwidth(), root.winfo_screenheight())
    saved = window_from(load_settings(), minimum, screen, VIEWS)
    size = saved.size or (px(theme.WINDOW_SIZE[0]), px(theme.WINDOW_SIZE[1]))
    root.geometry(f"{size[0]}x{size[1]}")
    root.minsize(*minimum)
    if saved.zoomed:
        _set_zoomed(root)
    return Window(root, manager, set_window_icon(root), saved)


def remember_window(root: tk.Tk, view: str) -> None:
    """Guarda el tamaño de la ventana, si está maximizada y la vista abierta.

    Args:
        root (tk.Tk): Ventana raíz (antes de destruirla).
        view (str): Vista visible.
    """
    zoomed = root.state() == _ZOOMED or bool(_attribute(root, "-zoomed"))
    save_window((root.winfo_width(), root.winfo_height()), zoomed, view)


def _set_zoomed(root: tk.Tk) -> None:
    """Maximiza la ventana (Windows usa el estado ``zoomed``; Linux, el atributo).

    Args:
        root (tk.Tk): Ventana raíz.
    """
    try:
        root.state(_ZOOMED)
    except tk.TclError:
        _attribute(root, "-zoomed", True)


def _attribute(root: tk.Tk, name: str, value: bool | None = None) -> object:
    """Lee o cambia un atributo de la ventana que no todos los sistemas tienen.

    Args:
        root (tk.Tk): Ventana raíz.
        name (str): Atributo (por ejemplo ``"-zoomed"``).
        value (bool | None): Valor nuevo; ``None`` para solo leerlo.

    Returns:
        object: Valor del atributo, o ``False`` si el sistema no lo tiene.
    """
    try:
        return root.attributes(name) if value is None else root.attributes(name, value)
    except tk.TclError:
        return False
