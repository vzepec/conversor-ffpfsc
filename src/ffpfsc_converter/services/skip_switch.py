"""Pedido de saltar un paso opcional de una conversión (por ejemplo, la verificación LZ4).

El pedido llega desde la interfaz mientras el paso corre en un hilo de fondo; por eso
usa ``threading.Event`` y solo se acepta mientras el paso en curso es opcional.
"""
from __future__ import annotations

import threading


class SkipSwitch:
    """Permite saltar el paso en curso solo mientras es opcional (la verificación LZ4)."""

    def __init__(self) -> None:
        """Empieza sin ningún paso que se pueda saltar."""
        self._allowed, self._requested = threading.Event(), threading.Event()

    def request(self) -> bool:
        """Pide saltar el paso en curso.

        Returns:
            bool: ``True`` si el paso en curso se puede saltar (hay que terminar su proceso).
        """
        if not self._allowed.is_set():
            return False
        self._requested.set()
        return True

    def begin(self) -> None:
        """Marca el comienzo de un paso que se puede saltar."""
        self._requested.clear()
        self._allowed.set()

    def end(self) -> bool:
        """Marca el final del paso opcional.

        Returns:
            bool: ``True`` si se pidió saltarlo.
        """
        self._allowed.clear()
        return self._requested.is_set()
