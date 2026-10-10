"""Piezas pequeñas: control segmentado, ficha con iniciales, punto de estado y botón con icono."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk

from PIL import ImageTk

from ffpfsc_converter.ui.theme import TILE_COLORS, Palette, ThemeManager
from ffpfsc_converter.ui.theme.shapes import render_circle, render_rounded


class Segmented(ttk.Frame):
    """Opciones excluyentes como un control segmentado de esquinas redondeadas."""

    def __init__(self, parent: tk.Misc, variable: tk.StringVar,
                 options: Sequence[tuple[str, str]], on_change: Callable[[], None] | None = None,
                 surface: str = "Card") -> None:
        """Crea un botón por opción.

        Args:
            parent (tk.Misc): Contenedor.
            variable (tk.StringVar): Variable con el valor elegido.
            options (Sequence[tuple[str, str]]): Pares (valor, texto visible).
            on_change (Callable[[], None] | None): Se llama al elegir otra opción.
            surface (str): Superficie sobre la que va (``"Card"``, ``"Side"`` o ``""``).
        """
        style = f"{surface}.SegBox.TFrame" if surface else "SegBox.TFrame"
        super().__init__(parent, style=style, padding=3)
        for value, text in options:
            ttk.Radiobutton(self, text=text, value=value, variable=variable,
                            style="Seg.Toolbutton", takefocus=False,
                            command=on_change or (lambda: None)).pack(side="left", fill="x",
                                                                      expand=True)


def initials(title: str) -> str:
    """Obtiene hasta dos iniciales de un título.

    Args:
        title (str): Nombre del juego.

    Returns:
        str: Iniciales en mayúsculas (``"SH"`` para "Silent Hill f"), o ``"?"``.
    """
    words = [w for w in title.replace("-", " ").split() if w[:1].isalnum()]
    letters = "".join(w[0] for w in words[:2]).upper()
    return letters or "?"


def tile_color(key: str) -> str:
    """Elige un color estable para la ficha de un juego.

    Args:
        key (str): Texto que identifica al juego (siempre da el mismo color).

    Returns:
        str: Color ``#rrggbb`` de ``TILE_COLORS``.
    """
    return TILE_COLORS[sum(key.encode("utf-8")) % len(TILE_COLORS)]


class Tile(tk.Canvas):
    """Ficha cuadrada de esquinas redondeadas con las iniciales del juego."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, surface: str = "surface",
                 size: int = 36) -> None:
        """Crea la ficha vacía.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema (fuente y escala).
            surface (str): Atributo de la paleta del fondo.
            size (int): Lado en píxeles lógicos.
        """
        self._size = theme.metrics.px(size)
        super().__init__(parent, width=self._size, height=self._size, highlightthickness=0, bd=0)
        self._theme, self._surface, self._title = theme, surface, ""
        self.show("")
        theme.on_change(lambda _p: self.show(self._title))

    def show(self, title: str, surface: str | None = None) -> None:
        """Dibuja las iniciales y el color del juego.

        Args:
            title (str): Nombre del juego.
            surface (str | None): Fondo nuevo (por ejemplo, al seleccionar la fila).
        """
        self._title, self._surface = title, surface or self._surface
        s, r = self._size, self._theme.metrics.px(8)
        self.delete("all")
        self.configure(background=getattr(self._theme.palette, self._surface))
        self._photo = ImageTk.PhotoImage(render_rounded((s, s), r, tile_color(title), None),
                                         master=self)
        self.create_image(0, 0, image=self._photo, anchor="nw")
        self.create_text(s / 2, s / 2, text=initials(title) if title else "",
                         fill="#ffffff", font=self._theme.fonts.small_bold)


class StatusDot(tk.Canvas):
    """Punto con halo que indica conexión (verde), espera (ámbar) o desconexión (gris)."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, surface: str) -> None:
        """Crea el punto.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            surface (str): Atributo de la paleta del fondo.
        """
        self._halo, self._dot = theme.metrics.px(3), theme.metrics.px(8)
        size = self._dot + 2 * self._halo
        super().__init__(parent, width=size, height=size, highlightthickness=0, bd=0)
        self._surface, self._state = surface, "off"
        self._photo: ImageTk.PhotoImage | None = None
        self._item = self.create_image(size / 2, size / 2)
        self._paint(theme.palette)
        theme.on_change(self._paint)

    def set_state(self, state: str, palette: Palette) -> None:
        """Cambia el estado del punto.

        Args:
            state (str): ``"on"``, ``"busy"`` u ``"off"``.
            palette (Palette): Paleta actual.
        """
        self._state = state
        self._paint(palette)

    def _paint(self, palette: Palette) -> None:
        """Pinta el punto y su halo con los colores de la paleta.

        Args:
            palette (Palette): Paleta actual.
        """
        color, halo = {"on": (palette.ok, palette.ok_soft),
                       "busy": (palette.warn, palette.warn_soft)}.get(
            self._state, (palette.muted, palette.surface2))
        self.configure(background=getattr(palette, self._surface))
        image = render_circle(self._dot, color, halo=(self._halo, halo))
        self._photo = ImageTk.PhotoImage(image, master=self)
        self.itemconfigure(self._item, image=self._photo)


def rounded_rect(canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float, r: float,
                 **options: object) -> int:
    """Dibuja un rectángulo de esquinas redondeadas en un lienzo.

    Args:
        canvas (tk.Canvas): Lienzo.
        x0 (float): Borde izquierdo.
        y0 (float): Borde superior.
        x1 (float): Borde derecho.
        y1 (float): Borde inferior.
        r (float): Radio de las esquinas.
        **options (object): Opciones del polígono (``fill``, ``outline``, ``tags``…).

    Returns:
        int: Identificador del polígono.
    """
    points = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
              x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(points, smooth=True, **options)


def icon_button(parent: tk.Misc, theme: ThemeManager, text: str, icon: str,
                command: Callable[[], None], style: str = "TButton",
                role: str = "text") -> ttk.Button:
    """Crea un botón con icono a la izquierda del texto (atenuado si se deshabilita).

    Args:
        parent (tk.Misc): Contenedor.
        theme (ThemeManager): Tema (iconos).
        text (str): Texto del botón.
        icon (str): Nombre del icono.
        command (Callable[[], None]): Acción del botón.
        style (str): Estilo ttk.
        role (str): Color del icono (atributo de la paleta).

    Returns:
        ttk.Button: Botón creado (sin ubicar).
    """
    size = 14 if "Small" in style else 16
    image = (theme.icons.get(icon, size, role), "disabled", theme.icons.get(icon, size, "muted"))
    return ttk.Button(parent, text=f" {text}" if text else "", image=image, compound="left",
                      command=command, style=style, takefocus=False)
