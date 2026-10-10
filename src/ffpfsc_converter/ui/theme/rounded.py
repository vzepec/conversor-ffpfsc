"""Catálogo de imágenes redondeadas del tema (botones, tarjetas, píldoras, campos y barras).

Cada imagen se crea una vez y, al cambiar de tema, se repinta en el mismo
objeto: los elementos ttk que la usan cambian de color sin recrearse.
"""
from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageTk

from ffpfsc_converter.ui.theme.palette import Palette
from ffpfsc_converter.ui.theme.shapes import RoundSpec, render_rounded

#: Estados de los botones, en el orden en que ttk los evalúa (gana el primero que aplica).
BUTTON_STATES = ("off", "pressed", "hover")
#: Tipos de botón → (relleno, borde) para normal, al pasar, pulsado y deshabilitado.
_BUTTON_COLORS: dict[str, tuple[tuple[str | None, str | None], ...]] = {
    "btn": (("surface", "line"), ("surface2", "line"), ("line", "line"), ("surface", "line")),
    "accent": (("accent", "accent"), ("accent_hover", "accent_hover"),
               ("accent_hover", "accent_hover"), ("accent_soft", "accent_soft")),
    "ghost": ((None, "line"), ("surface2", "line"), ("line", "line"), (None, "line")),
    "danger": (("surface", "line"), ("bad_soft", "line"), ("bad_soft", "bad"),
               ("surface", "line")),
    "flat": ((None, None), ("surface2", None), ("line", None), (None, None)),
    "success": (("ok_soft", "ok_soft"), ("ok_soft", "ok"), ("ok_soft", "ok"),
                ("ok_soft", "ok_soft")),
}
_BUTTON_WIDTH, _BUTTON_HEIGHT, _BUTTON_RADIUS = 96, 24, 8


def _button_specs() -> dict[str, RoundSpec]:
    """Genera las formas de cada tipo y estado de botón.

    Returns:
        dict[str, RoundSpec]: ``"accent"``, ``"accent.hover"``, ``"accent.pressed"``…
    """
    specs: dict[str, RoundSpec] = {}
    for kind, colors in _BUTTON_COLORS.items():
        for state, (fill, outline) in zip(("", "hover", "pressed", "off"), colors, strict=True):
            name = f"{kind}.{state}" if state else kind
            specs[name] = RoundSpec(_BUTTON_WIDTH, _BUTTON_HEIGHT, _BUTTON_RADIUS, fill, outline)
    return specs


SPECS: dict[str, RoundSpec] = {
    **_button_specs(),
    # Contenedores.
    "card": RoundSpec(160, 96, 10, "surface", "line"),
    "bar": RoundSpec(160, 40, 10, "surface2", "line"),
    "nav": RoundSpec(128, 34, 8, "accent_soft"),
    "badge": RoundSpec(40, 40, 10, "accent_soft"),
    "path": RoundSpec(160, 28, 8, "surface", "line"),
    "field": RoundSpec(96, 26, 7, "surface2", "line"),
    "field.focus": RoundSpec(96, 26, 7, "surface2", "accent"),
    # Control segmentado: caja y opción elegida.
    "segbox": RoundSpec(160, 30, 8, "surface2", "line"),
    "seg.on": RoundSpec(96, 24, 6, "surface", "line"),
    "seg.off": RoundSpec(96, 24, 6, None),
    # Píldoras de estado.
    "pill.wait": RoundSpec(72, 20, 9, "surface2"),
    "pill.run": RoundSpec(72, 20, 9, "accent_soft"),
    "pill.ok": RoundSpec(72, 20, 9, "ok_soft"),
    "pill.warn": RoundSpec(72, 20, 9, "warn_soft"),
    "pill.bad": RoundSpec(72, 20, 9, "bad_soft"),
    # Barras de progreso y de desplazamiento.
    "trough": RoundSpec(160, 7, 3, "surface2"),
    "pbar.accent": RoundSpec(160, 7, 3, "accent"),
    "pbar.ok": RoundSpec(160, 7, 3, "ok"),
    "pbar.warn": RoundSpec(160, 7, 3, "warn"),
    "thumb": RoundSpec(12, 96, 3, "line", inset=2),
    "thumb.hover": RoundSpec(12, 96, 3, "muted", inset=2),
}


class RoundedImages:
    """Imágenes redondeadas del tema, escaladas a la pantalla."""

    def __init__(self, root: tk.Misc, scale: float, palette: Palette) -> None:
        """Dibuja todas las imágenes con la paleta inicial.

        Args:
            root (tk.Misc): Ventana raíz (dueña de las imágenes).
            scale (float): Factor de escala de la pantalla.
            palette (Palette): Paleta actual.
        """
        self._scale = scale
        self._images = {name: ImageTk.PhotoImage(self._render(spec, palette), master=root)
                        for name, spec in SPECS.items()}

    def get(self, name: str) -> ImageTk.PhotoImage:
        """Obtiene una imagen del catálogo.

        Args:
            name (str): Clave de ``SPECS``.

        Returns:
            ImageTk.PhotoImage: Imagen lista para un elemento ttk.

        Raises:
            KeyError: Si la imagen no existe.
        """
        return self._images[name]

    def border(self, name: str) -> int:
        """Calcula cuántos píxeles de cada lado no se estiran.

        Args:
            name (str): Clave de ``SPECS``.

        Returns:
            int: Borde fijo en píxeles reales.
        """
        return self.border_of(SPECS[name])

    def repaint(self, palette: Palette) -> None:
        """Vuelve a pintar todas las imágenes con otra paleta.

        Args:
            palette (Palette): Paleta nueva.
        """
        for name, photo in self._images.items():
            photo.paste(self._render(SPECS[name], palette))

    def _render(self, spec: RoundSpec, palette: Palette) -> Image.Image:
        """Dibuja una forma con los colores de la paleta.

        Args:
            spec (RoundSpec): Forma a dibujar.
            palette (Palette): Paleta del tema.

        Returns:
            Image.Image: Imagen RGBA escalada.
        """
        fill = getattr(palette, spec.fill) if spec.fill else None
        outline = getattr(palette, spec.outline) if spec.outline else None
        minimum = 2 * self.border_of(spec) + 1
        size = (max(minimum, round(spec.width * self._scale)),
                max(minimum, round(spec.height * self._scale)))
        return render_rounded(size, spec.radius * self._scale, fill, outline,
                              spec.inset * self._scale)

    def border_of(self, spec: RoundSpec) -> int:
        """Calcula el borde fijo de una forma a la escala actual.

        Args:
            spec (RoundSpec): Forma.

        Returns:
            int: Borde en píxeles reales.
        """
        return round(spec.border * self._scale)
