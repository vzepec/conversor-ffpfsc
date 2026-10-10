"""Ajuste de textos al ancho disponible."""
from __future__ import annotations

from typing import Protocol


class TextMeasurer(Protocol):
    """Fuente capaz de medir textos (por ejemplo, ``tkinter.font.Font``)."""

    def measure(self, text: str) -> int:
        """Mide el ancho de un texto.

        Args:
            text (str): Texto a medir.

        Returns:
            int: Ancho en píxeles.
        """
        ...


def elide(text: str, font: TextMeasurer, width: int) -> str:
    """Recorta un texto con «…» para que quepa en un ancho.

    Args:
        text (str): Texto completo.
        font (TextMeasurer): Fuente con la que se dibuja.
        width (int): Ancho disponible en píxeles.

    Returns:
        str: El texto, o su comienzo seguido de «…».
    """
    if font.measure(text) <= width:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if font.measure(text[:middle] + "…") <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low] + "…"
