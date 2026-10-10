"""Creación de la ventana principal: escala, identidad en el sistema, tema, tamaño e icono."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

from PIL import ImageTk

from ffpfsc_converter.config import WINDOW_CLASS, WINDOWS_APP_ID
from ffpfsc_converter.infrastructure.system import enable_dpi_awareness, set_windows_app_id
from ffpfsc_converter.ui import presenters, theme
from ffpfsc_converter.ui.dnd import create_root
from ffpfsc_converter.ui.theme.app_icon import set_window_icon


@dataclass
class Window:
    """Ventana raíz lista para construir las vistas.

    Attributes:
        root (tk.Tk): Ventana raíz.
        theme (theme.ThemeManager): Tema aplicado.
        icons (list[ImageTk.PhotoImage]): Imágenes del icono (se conservan mientras viva).
    """

    root: tk.Tk
    theme: theme.ThemeManager
    icons: list[ImageTk.PhotoImage]


def create_window() -> Window:
    """Crea la ventana con su título, tema, tamaño inicial e icono.

    Returns:
        Window: Ventana y tema listos.
    """
    enable_dpi_awareness()
    set_windows_app_id(WINDOWS_APP_ID)
    root = create_root(WINDOW_CLASS)
    root.title(presenters.window_title())
    manager = theme.ThemeManager(root)
    px = manager.metrics.px
    root.geometry("{}x{}".format(*map(px, theme.WINDOW_SIZE)))
    root.minsize(*map(px, theme.WINDOW_MIN_SIZE))
    return Window(root, manager, set_window_icon(root))
