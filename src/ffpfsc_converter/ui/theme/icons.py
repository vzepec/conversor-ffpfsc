"""Iconos de la interfaz dibujados con Pillow y teñidos según el tema.

Cada icono se dibuja a 4× y se reduce con suavizado, así queda nítido a
cualquier escala. Las imágenes se guardan en caché y, al cambiar de tema, se
repintan en el mismo objeto: los widgets que las usan se actualizan solos.
"""
from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from ffpfsc_converter.ui.theme.icon_shapes import SHAPES
from ffpfsc_converter.ui.theme.palette import Palette

_SUPERSAMPLE = 4
_GRID = 24.0
_STROKE = 1.9


def render_icon(name: str, size: int, color: str) -> Image.Image:
    """Dibuja un icono de línea.

    Args:
        name (str): Nombre del icono (clave de ``SHAPES``).
        size (int): Lado en píxeles.
        color (str): Color del trazo (``#rrggbb``).

    Returns:
        Image.Image: Imagen RGBA con fondo transparente.

    Raises:
        KeyError: Si el icono no existe.
    """
    big = size * _SUPERSAMPLE
    scale = big / _GRID
    width = max(1, round(_STROKE * scale))
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for stroke in SHAPES[name]:
        kind = stroke[0]
        if kind == "line":
            points = [(x * scale, y * scale) for x, y in stroke[1]]
            draw.line(points, fill=color, width=width, joint="curve")
            for x, y in (points[0], points[-1]):  # extremos redondeados
                draw.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2),
                             fill=color)
        elif kind == "rect":
            x0, y0, x1, y1, radius = (v * scale for v in stroke[1:])
            draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, outline=color, width=width)
        elif kind == "arc":
            cx, cy, r = (v * scale for v in stroke[1:4])
            draw.arc((cx - r, cy - r, cx + r, cy + r), stroke[4], stroke[5], fill=color,
                     width=width)
        elif kind == "dot":
            cx, cy, r = (v * scale for v in stroke[1:4])
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def render_switch(on: bool, width: int, height: int, palette: Palette) -> Image.Image:
    """Dibuja el interruptor de las casillas de verificación.

    Args:
        on (bool): ``True`` para el estado activado.
        width (int): Ancho en píxeles.
        height (int): Alto en píxeles.
        palette (Palette): Paleta del tema.

    Returns:
        Image.Image: Imagen RGBA del interruptor.
    """
    k = _SUPERSAMPLE
    w, h = width * k, height * k
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=h / 2,
                           fill=palette.accent if on else palette.line)
    pad = h * 0.14
    knob = h - 2 * pad
    x0 = w - pad - knob if on else pad
    draw.ellipse((x0, pad, x0 + knob, pad + knob), fill="#ffffff")
    return image.resize((width, height), Image.Resampling.LANCZOS)


class IconSet:
    """Caché de iconos que se repintan al cambiar de tema."""

    def __init__(self, root: tk.Misc, scale: float, palette: Palette) -> None:
        """Prepara la caché.

        Args:
            root (tk.Misc): Ventana raíz (dueña de las imágenes).
            scale (float): Factor de escala de la pantalla (1.0 = 96 ppp).
            palette (Palette): Paleta actual.
        """
        self._root = root
        self._scale = scale
        self._palette = palette
        self._icons: dict[tuple[str, int, str], ImageTk.PhotoImage] = {}
        self._switches: dict[bool, ImageTk.PhotoImage] = {}

    def get(self, name: str, size: int = 16, role: str = "muted") -> ImageTk.PhotoImage:
        """Obtiene un icono del tamaño y color pedidos (lo crea la primera vez).

        Args:
            name (str): Nombre del icono.
            size (int): Lado en píxeles lógicos (se multiplica por la escala).
            role (str): Color de la paleta (``"muted"``, ``"text"``, ``"accent"``…).

        Returns:
            ImageTk.PhotoImage: Imagen lista para usar en un widget.
        """
        key = (name, size, role)
        if key not in self._icons:
            pixels = max(8, round(size * self._scale))
            image = render_icon(name, pixels, getattr(self._palette, role))
            self._icons[key] = ImageTk.PhotoImage(image, master=self._root)
        return self._icons[key]

    def switch(self, on: bool) -> ImageTk.PhotoImage:
        """Obtiene la imagen del interruptor (activado o no).

        Args:
            on (bool): Estado del interruptor.

        Returns:
            ImageTk.PhotoImage: Imagen del interruptor.
        """
        if on not in self._switches:
            self._switches[on] = ImageTk.PhotoImage(self._switch_image(on), master=self._root)
        return self._switches[on]

    def repaint(self, palette: Palette) -> None:
        """Vuelve a pintar todos los iconos con los colores de otra paleta.

        Args:
            palette (Palette): Paleta nueva.
        """
        self._palette = palette
        for (name, _size, role), photo in self._icons.items():
            photo.paste(render_icon(name, photo.width(), getattr(palette, role)))
        for on, photo in self._switches.items():
            photo.paste(self._switch_image(on))

    def _switch_image(self, on: bool) -> Image.Image:
        """Dibuja el interruptor al tamaño de la pantalla.

        Args:
            on (bool): Estado del interruptor.

        Returns:
            Image.Image: Imagen del interruptor.
        """
        return render_switch(on, round(32 * self._scale), round(18 * self._scale), self._palette)
