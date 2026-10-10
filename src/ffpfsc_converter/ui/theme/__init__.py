"""Tema visual de la app: paletas, fuentes, iconos, escala y estilos ttk.

Solo la capa ``ui`` lo usa. Las medidas generales de la ventana viven aquí.
"""
from ffpfsc_converter.ui.theme.manager import MODES, ThemeManager, resolve_palette
from ffpfsc_converter.ui.theme.palette import DARK, LIGHT, TILE_COLORS, Palette

#: Tamaño inicial y mínimo de la ventana (píxeles lógicos).
WINDOW_SIZE = (1180, 780)
WINDOW_MIN_SIZE = (1040, 660)
#: Ancho de la barra lateral (píxeles lógicos).
SIDEBAR_WIDTH = 232
#: Separación estándar entre bloques de la vista PS5 (píxeles lógicos).
PADDING = {"padx": 10, "pady": 6}
#: Intervalo (ms) con el que la UI vacía la cola de eventos.
EVENT_POLL_MS = 100

__all__ = [
    "DARK",
    "EVENT_POLL_MS",
    "LIGHT",
    "MODES",
    "PADDING",
    "SIDEBAR_WIDTH",
    "TILE_COLORS",
    "WINDOW_MIN_SIZE",
    "WINDOW_SIZE",
    "Palette",
    "ThemeManager",
    "resolve_palette",
]
