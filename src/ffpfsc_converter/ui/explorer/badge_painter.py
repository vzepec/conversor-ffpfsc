"""Dibuja las etiquetas de tipo («Juego», «LZ4», «Comprimido»…) de la lista de la PS5."""
from __future__ import annotations

import tkinter as tk

from PIL import ImageTk

from ffpfsc_converter.ui.explorer.view_presenters import Badge
from ffpfsc_converter.ui.theme import Palette, ThemeManager
from ffpfsc_converter.ui.theme.shapes import render_rounded

#: Fondo y texto (atributos de la paleta) de cada tipo de etiqueta.
_BADGE_COLORS = {"wait": ("surface2", "muted"), "ok": ("ok_soft", "ok"),
                 "warn": ("warn_soft", "warn")}


class BadgePainter:
    """Dibuja etiquetas redondeadas en un lienzo, guardando sus fondos para reutilizarlos."""

    def __init__(self, master: tk.Misc, theme: ThemeManager) -> None:
        """Prepara el dibujante sin fondos guardados.

        Args:
            master (tk.Misc): Dueño de las imágenes (el lienzo o su contenedor).
            theme (ThemeManager): Tema (fuentes y escala).
        """
        self._master, self._theme = master, theme
        self._images: dict[tuple[int, int, str], ImageTk.PhotoImage] = {}

    def width(self, badge: Badge | None) -> int:
        """Calcula el ancho que ocupa una etiqueta.

        Args:
            badge (Badge | None): Etiqueta, o ``None`` si el elemento no tiene.

        Returns:
            int: Ancho en píxeles (``0`` sin etiqueta).
        """
        if badge is None:
            return 0
        return self._theme.fonts.small_bold.measure(badge.text) + self._theme.metrics.px(14)

    def draw(self, canvas: tk.Canvas, badge: Badge, position: tuple[float, float],
             palette: Palette) -> None:
        """Dibuja una etiqueta con su borde izquierdo en ``position``.

        Args:
            canvas (tk.Canvas): Lienzo.
            badge (Badge): Etiqueta.
            position (tuple[float, float]): Borde izquierdo y centro vertical.
            palette (Palette): Paleta actual.
        """
        x, middle = position
        width = self.width(badge)
        fill, ink = (getattr(palette, a) for a in _BADGE_COLORS[badge.kind])
        canvas.create_image(x, middle, anchor="w",
                            image=self._image(width, self._theme.metrics.px(18), fill))
        canvas.create_text(x + width / 2, middle, text=badge.text, fill=ink,
                           font=self._theme.fonts.small_bold)

    def _image(self, width: int, height: int, color: str) -> ImageTk.PhotoImage:
        """Obtiene (y guarda) el fondo redondeado y suavizado de una etiqueta.

        Args:
            width (int): Ancho en píxeles.
            height (int): Alto en píxeles.
            color (str): Color de relleno.

        Returns:
            ImageTk.PhotoImage: Imagen lista para el lienzo.
        """
        key = (width, height, color)
        if key not in self._images:
            image = render_rounded((width, height), self._theme.metrics.px(5), color, None)
            self._images[key] = ImageTk.PhotoImage(image, master=self._master)
        return self._images[key]
