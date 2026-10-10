"""Gestor del tema: elige claro u oscuro, aplica los estilos y avisa de los cambios.

El modo se guarda en los ajustes: ``"system"`` (por defecto, sigue al sistema
operativo y detecta sus cambios mientras la app está abierta), ``"light"`` o ``"dark"``.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.infrastructure.settings_store import load_settings, save_settings
from ffpfsc_converter.infrastructure.system import system_prefers_dark
from ffpfsc_converter.ui.theme.fonts import create_fonts
from ffpfsc_converter.ui.theme.icons import IconSet
from ffpfsc_converter.ui.theme.metrics import Metrics
from ffpfsc_converter.ui.theme.palette import DARK, LIGHT, Palette
from ffpfsc_converter.ui.theme.round_styles import apply_round_styles
from ffpfsc_converter.ui.theme.rounded import RoundedImages
from ffpfsc_converter.ui.theme.styles import apply_base_styles
from ffpfsc_converter.ui.theme.widget_styles import apply_widget_styles, ensure_switch_style

MODES = ("system", "light", "dark")
_SETTINGS_KEY = "ui_theme"
_FOLLOW_MS = 4000

#: Recibe la paleta nueva tras un cambio de tema.
ThemeListener = Callable[[Palette], None]


def resolve_palette(mode: str, prefers_dark: bool | None) -> Palette:
    """Elige la paleta según el modo y la preferencia del sistema.

    Args:
        mode (str): ``"system"``, ``"light"`` o ``"dark"``.
        prefers_dark (bool | None): Preferencia del sistema; ``None`` si se desconoce.

    Returns:
        Palette: Oscura si el modo es oscuro, o si es "sistema" y el sistema es
        oscuro o se desconoce; clara en los demás casos.
    """
    if mode == "light":
        return LIGHT
    if mode == "dark":
        return DARK
    return LIGHT if prefers_dark is False else DARK


class ThemeManager:
    """Estado del tema de la ventana.

    Attributes:
        mode (str): Modo elegido por el usuario.
        palette (Palette): Paleta aplicada.
        fonts (Fonts): Fuentes de la app.
        metrics (Metrics): Escala de la pantalla.
        icons (IconSet): Iconos teñidos según el tema.
    """

    def __init__(self, root: tk.Tk) -> None:
        """Crea fuentes, métricas e iconos y aplica el tema guardado.

        Args:
            root (tk.Tk): Ventana raíz.
        """
        self._root = root
        self._style = ttk.Style(root)
        self._style.theme_use("clam")
        self._listeners: list[ThemeListener] = []
        saved = str(load_settings().get(_SETTINGS_KEY, "system"))
        self.mode = saved if saved in MODES else "system"
        self.metrics = Metrics.from_root(root)
        self.fonts = create_fonts(root)
        self.palette = resolve_palette(self.mode, system_prefers_dark())
        self.icons = IconSet(root, self.metrics.scale, self.palette)
        self._shapes = RoundedImages(root, self.metrics.scale, self.palette)
        self._apply()
        root.after(_FOLLOW_MS, self._follow_system)

    def on_change(self, listener: ThemeListener) -> None:
        """Registra una función que se llama al cambiar de tema.

        Sirve para los widgets que no son ttk (Canvas, Text) y pintan sus colores a mano.

        Args:
            listener (ThemeListener): Recibe la paleta nueva.
        """
        self._listeners.append(listener)

    def set_mode(self, mode: str) -> None:
        """Cambia el modo, lo guarda y aplica la paleta correspondiente.

        Args:
            mode (str): ``"system"``, ``"light"`` o ``"dark"``.

        Raises:
            ValueError: Si el modo no es válido.
        """
        if mode not in MODES:
            raise ValueError(f"modo de tema desconocido: {mode}")
        self.mode = mode
        save_settings({_SETTINGS_KEY: mode})
        self._switch_to(resolve_palette(mode, system_prefers_dark()))

    def switch_style(self, surface: str) -> str:
        """Prepara el estilo de interruptor para una superficie.

        Args:
            surface (str): Atributo de la paleta del fondo (por ejemplo ``"surface"``).

        Returns:
            str: Nombre del estilo a usar en ``ttk.Checkbutton``.
        """
        ensure_switch_style(self._style, self.icons, self.palette, self.fonts,
                            getattr(self.palette, surface))
        return "Switch.TCheckbutton"

    def _switch_to(self, palette: Palette) -> None:
        """Aplica otra paleta si es distinta de la actual.

        Args:
            palette (Palette): Paleta nueva.
        """
        if palette is self.palette:
            return
        self.palette = palette
        self.icons.repaint(palette)
        self._shapes.repaint(palette)
        self._apply()
        for listener in list(self._listeners):
            try:
                listener(palette)
            except tk.TclError:  # el widget se destruyó (por ejemplo, un diálogo cerrado)
                self._listeners.remove(listener)

    def _apply(self) -> None:
        """Aplica estilos y colores base de la ventana con la paleta actual."""
        apply_base_styles(self._style, self.palette, self.fonts)
        apply_round_styles(self._style, self._shapes, self.palette, self.fonts, self.metrics)
        apply_widget_styles(self._style, self._shapes, self.palette, self.fonts, self.metrics)
        ensure_switch_style(self._style, self.icons, self.palette, self.fonts,
                            self.palette.surface)
        self._root.configure(background=self.palette.bg)
        self._root.option_add("*Toplevel.background", self.palette.bg)

    def _follow_system(self) -> None:
        """Cambia de paleta si el sistema cambió de tema (solo en modo "sistema")."""
        if self.mode == "system":
            self._switch_to(resolve_palette(self.mode, system_prefers_dark()))
        self._root.after(_FOLLOW_MS, self._follow_system)
