"""Compatibilidad de un juego con la compresión LZ4 (formato AMPR)."""
from __future__ import annotations

from enum import Enum


class Lz4Compat(Enum):
    """Si el juego puede usar el formato AMPR (se decide leyendo sus ejecutables)."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"
