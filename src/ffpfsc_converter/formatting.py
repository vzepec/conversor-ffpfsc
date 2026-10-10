"""Formatos de texto compartidos por varias capas (sin dependencias)."""
from __future__ import annotations

_SIZE_UNITS = ("B", "KB", "MB", "GB")
_LAST_SIZE_UNIT = "TB"


def format_size(n: float) -> str:
    """Convierte bytes en un tamaño legible en base 1024.

    Args:
        n (float): Cantidad de bytes.

    Returns:
        str: Tamaño con un decimal y unidad, por ejemplo ``"1.5 KB"``.
    """
    for unit in _SIZE_UNITS:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} {_LAST_SIZE_UNIT}"
