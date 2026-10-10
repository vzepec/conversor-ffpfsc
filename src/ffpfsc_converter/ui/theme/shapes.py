"""Dibujo de rectángulos redondeados con Pillow (funciones puras).

Tk no sabe redondear las esquinas de los widgets ttk. Para lograrlo, cada
botón, tarjeta, píldora o campo usa una imagen redondeada que ttk estira en
9 partes (las esquinas no se deforman). Tk rellena la parte central repitiendo
la imagen, así que las imágenes son anchas: cuantas menos repeticiones, más
rápido se redibuja la ventana al cambiar de tema.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

_SUPERSAMPLE = 4
_ARC_STEPS = 16


@dataclass(frozen=True)
class RoundSpec:
    """Forma de una imagen redondeada, en píxeles lógicos.

    Attributes:
        width (int): Ancho de la imagen.
        height (int): Alto de la imagen.
        radius (int): Radio de las esquinas.
        fill (str | None): Atributo de la paleta del relleno; ``None`` = transparente.
        outline (str | None): Atributo de la paleta del borde; ``None`` = sin borde.
        inset (int): Margen transparente alrededor de la forma.
    """

    width: int
    height: int
    radius: int
    fill: str | None
    outline: str | None = None
    inset: int = 0

    @property
    def border(self) -> int:
        """Calcula el borde que no se estira (esquinas más el margen).

        Returns:
            int: Píxeles lógicos fijos en cada lado de la imagen.
        """
        return self.radius + self.inset


def render_rounded(size: tuple[int, int], radius: float, fill: str | None,
                   outline: str | None, inset: float = 0) -> Image.Image:
    """Dibuja un rectángulo redondeado con bordes suavizados.

    Args:
        size (tuple[int, int]): Ancho y alto de la imagen en píxeles reales.
        radius (float): Radio de las esquinas en píxeles reales.
        fill (str | None): Color de relleno (``#rrggbb``) o ``None`` para dejarlo transparente.
        outline (str | None): Color del borde de 1 px o ``None`` para no dibujarlo.
        inset (float): Margen transparente alrededor de la forma, en píxeles reales.

    Returns:
        Image.Image: Imagen RGBA con las esquinas transparentes.
    """
    k = _SUPERSAMPLE
    width, height = size
    if fill is None and outline is None:
        return Image.new("RGBA", size, (0, 0, 0, 0))
    image = Image.new("RGBA", (width * k, height * k), (0, 0, 0, 0))
    box = (inset * k, inset * k, width * k - 1 - inset * k, height * k - 1 - inset * k)
    ImageDraw.Draw(image).rounded_rectangle(box, radius=radius * k, fill=fill, outline=outline,
                                            width=k if outline else 0)
    return image.resize(size, Image.Resampling.LANCZOS)


def render_circle(diameter: int, fill: str, outline: str | None = None, border: float = 0,
                  halo: tuple[int, str] | None = None) -> Image.Image:
    """Dibuja un círculo con bordes suavizados (Tk dibuja los óvalos sin suavizar).

    Args:
        diameter (int): Diámetro del círculo en píxeles reales.
        fill (str): Color de relleno.
        outline (str | None): Color del borde, o ``None`` para no dibujarlo.
        border (float): Grosor del borde en píxeles reales.
        halo (tuple[int, str] | None): Grosor y color de un anillo exterior, si lleva.

    Returns:
        Image.Image: Imagen RGBA cuadrada de lado ``diameter`` más dos veces el halo.
    """
    k = _SUPERSAMPLE
    ring, ring_color = halo if halo else (0, "")
    side = diameter + 2 * ring
    image = Image.new("RGBA", (side * k, side * k), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if ring:
        draw.ellipse((0, 0, side * k - 1, side * k - 1), fill=ring_color)
    box = (ring * k, ring * k, (ring + diameter) * k - 1, (ring + diameter) * k - 1)
    draw.ellipse(box, fill=fill, outline=outline, width=round(border * k) if outline else 0)
    return image.resize((side, side), Image.Resampling.LANCZOS)


def render_dashed_card(size: tuple[int, int], radius: float, fill: str,
                       outline: tuple[str, float], dash: tuple[float, float]) -> Image.Image:
    """Dibuja una tarjeta redondeada con borde punteado y suavizado.

    Args:
        size (tuple[int, int]): Ancho y alto en píxeles reales.
        radius (float): Radio de las esquinas.
        fill (str): Color del relleno.
        outline (tuple[str, float]): Color y grosor del borde.
        dash (tuple[float, float]): Largo de cada trazo y de cada hueco.

    Returns:
        Image.Image: Imagen RGBA con las esquinas transparentes.
    """
    k = _SUPERSAMPLE
    color, width = outline
    image = Image.new("RGBA", (size[0] * k, size[1] * k), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = width * k / 2
    box = (inset, inset, size[0] * k - 1 - inset, size[1] * k - 1 - inset)
    draw.rounded_rectangle(box, radius=radius * k, fill=fill)
    path = _rounded_path(box, radius * k)
    for segment in _dash_segments(path, dash[0] * k, dash[1] * k):
        draw.line(segment, fill=color, width=max(1, round(width * k)), joint="curve")
    return image.resize(size, Image.Resampling.LANCZOS)


def _rounded_path(box: tuple[float, float, float, float],
                  radius: float) -> list[tuple[float, float]]:
    """Calcula el contorno de un rectángulo redondeado como lista de puntos (horario).

    Args:
        box (tuple[float, float, float, float]): Bordes izquierdo, superior, derecho e inferior.
        radius (float): Radio de las esquinas.

    Returns:
        list[tuple[float, float]]: Puntos del contorno; el último repite el primero.
    """
    x0, y0, x1, y1 = box
    corners = ((x0 + radius, y0 + radius, 180), (x1 - radius, y0 + radius, 270),
               (x1 - radius, y1 - radius, 0), (x0 + radius, y1 - radius, 90))
    points = []
    for cx, cy, start in corners:
        for step in range(_ARC_STEPS + 1):
            angle = math.radians(start + 90 * step / _ARC_STEPS)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return [*points, points[0]]


def _dash_segments(path: list[tuple[float, float]], dash: float,
                   gap: float) -> list[list[tuple[float, float]]]:
    """Corta un contorno en trazos y huecos de largo fijo.

    Args:
        path (list[tuple[float, float]]): Puntos del contorno.
        dash (float): Largo de cada trazo.
        gap (float): Largo de cada hueco.

    Returns:
        list[list[tuple[float, float]]]: Puntos de cada trazo visible.
    """
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = [path[0]]
    drawing, left = True, dash
    for (ax, ay), (bx, by) in itertools.pairwise(path):
        length = math.hypot(bx - ax, by - ay)
        done = 0.0
        while length - done > left:
            done += left
            point = (ax + (bx - ax) * done / length, ay + (by - ay) * done / length)
            if drawing:
                segments.append([*current, point])
            current = [point]
            drawing, left = not drawing, gap if drawing else dash
        left -= length - done
        if drawing:
            current.append((bx, by))
        else:
            current = [(bx, by)]
    if drawing and len(current) > 1:
        segments.append(current)
    return segments
