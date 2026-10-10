"""Icono de la app: cuadrado azul redondeado con tres barras (datos comprimidos).

Se dibuja con Pillow a cualquier tamaño: lo usan la ventana, la barra lateral
y ``tools/make_icon.py`` para generar los archivos de los accesos directos.
"""
from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

#: Colores de la marca (no cambian con el tema): degradado de arriba a abajo.
_TOP, _BOTTOM = (91, 155, 255), (40, 102, 224)
_BARS = (("#ffffff", 0.52), ("#ffffff", 0.38), ("#c9dbff", 0.24))
_SUPERSAMPLE = 4
#: Tamaños del icono de la ventana (Windows y Linux eligen el que mejor les queda).
WINDOW_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_app_icon(size: int) -> Image.Image:
    """Dibuja el icono de la app.

    Args:
        size (int): Lado en píxeles.

    Returns:
        Image.Image: Imagen RGBA con las esquinas transparentes.
    """
    big = size * _SUPERSAMPLE
    gradient = Image.new("RGBA", (1, big))
    for y in range(big):
        t = y / max(big - 1, 1)
        rgb = (round(a + (b - a) * t) for a, b in zip(_TOP, _BOTTOM, strict=True))
        gradient.putpixel((0, y), (*rgb, 255))
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=big * 0.23,
                                           fill=255)
    image.paste(gradient.resize((big, big)), (0, 0), mask)
    draw = ImageDraw.Draw(image)
    bar = big * 0.09
    for index, (color, width) in enumerate(_BARS):
        top = big * (0.29 + index * 0.16)
        draw.rounded_rectangle((big * 0.24, top, big * (0.24 + width), top + bar),
                               radius=bar / 2, fill=color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def set_window_icon(root: tk.Tk) -> list[ImageTk.PhotoImage]:
    """Pone el icono en la ventana (barra de título y barra de tareas).

    Args:
        root (tk.Tk): Ventana raíz.

    Returns:
        list[ImageTk.PhotoImage]: Imágenes usadas; hay que conservarlas mientras viva la
        ventana (Tk no guarda una referencia propia).
    """
    photos = [ImageTk.PhotoImage(render_app_icon(size), master=root)
              for size in WINDOW_ICON_SIZES]
    root.iconphoto(True, *photos)
    return photos
