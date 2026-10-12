"""Formatos de texto compartidos por varias capas (sin dependencias)."""
from __future__ import annotations

from ffpfsc_converter.config import LZ4_VERIFY_PHASE

_SIZE_UNITS = ("B", "KB", "MB", "GB")
_LAST_SIZE_UNIT = "TB"
#: Nombres en español de las fases de MkPFS.
PHASE_NAMES = {
    "compress": "Comprimiendo",
    "write": "Escribiendo",
    "scan": "Escaneando",
    "verify": "Verificando",
    LZ4_VERIFY_PHASE: "Verificando",
}


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


def format_eta(seconds: float | None) -> str:
    """Formatea un tiempo restante aproximado.

    Args:
        seconds (float | None): Segundos restantes, o ``None`` si se desconoce.

    Returns:
        str: Por ejemplo ``"quedan ≈ 45 s"``, ``"quedan ≈ 3 min 20 s"`` o
        ``"quedan ≈ 1 h 05 min"``; vacío si se desconoce.
    """
    if seconds is None:
        return ""
    total = round(seconds)
    if total < 60:
        return f"quedan ≈ {max(total, 1)} s"
    if total < 600:  # menos de 10 min: en pasos de 10 s
        minutes, secs = divmod(round(total / 10) * 10, 60)
        return f"quedan ≈ {minutes} min {secs:02d} s"
    minutes = round(total / 60)
    if minutes < 60:
        return f"quedan ≈ {minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"quedan ≈ {hours} h {minutes:02d} min"
