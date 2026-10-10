"""Dibujo de rectángulos redondeados con Pillow (funciones puras).

Tk no sabe redondear las esquinas de los widgets ttk. Para lograrlo, cada
botón, tarjeta, píldora o campo usa una imagen redondeada que ttk estira en
9 partes (las esquinas no se deforman). Tk rellena la parte central repitiendo
la imagen, así que las imágenes son anchas: cuantas menos repeticiones, más
rápido se redibuja la ventana al cambiar de tema.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

_SUPERSAMPLE = 4


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
