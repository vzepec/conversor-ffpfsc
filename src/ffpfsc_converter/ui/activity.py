"""Vigila si hay tareas largas en curso para que el equipo no se suspenda."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from ffpfsc_converter.infrastructure.power import SleepInhibitor

_POLL_MS = 1000
_REASON = "Conversión o transferencia con la PS5 en curso"


class ActivityWatch:
    """Bloquea la suspensión mientras ``is_busy`` devuelva ``True``."""

    def __init__(self, root: tk.Misc, is_busy: Callable[[], bool],
                 inhibitor: SleepInhibitor | None = None) -> None:
        """Empieza a vigilar.

        Args:
            root (tk.Misc): Ventana principal (programa las consultas).
            is_busy (Callable[[], bool]): Indica si hay una tarea larga en curso.
            inhibitor (SleepInhibitor | None): Bloqueo a usar; ``None`` = el del sistema.
        """
        self._root, self._is_busy = root, is_busy
        self._inhibitor = inhibitor or SleepInhibitor()
        self._root.after(_POLL_MS, self._tick)

    def stop(self) -> None:
        """Libera el bloqueo (al cerrar la app)."""
        self._inhibitor.release()

    def _tick(self) -> None:
        """Bloquea o libera según haya tareas, y se vuelve a programar."""
        if self._is_busy():
            self._inhibitor.acquire(_REASON)
        else:
            self._inhibitor.release()
        self._root.after(_POLL_MS, self._tick)
