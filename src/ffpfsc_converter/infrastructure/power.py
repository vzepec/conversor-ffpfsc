"""Evita que el equipo se suspenda mientras hay tareas largas (Linux y Windows).

- Linux: mantiene vivo ``systemd-inhibit … sleep infinity``; el bloqueo dura lo
  que dure ese proceso.
- Windows: ``SetThreadExecutionState`` con ``ES_SYSTEM_REQUIRED``; se llama siempre
  desde el mismo hilo (el de la interfaz), porque el estado es por hilo.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable

from ffpfsc_converter.config import APP_TITLE

_ES_CONTINUOUS, _ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
_INHIBIT_TOOL = "systemd-inhibit"


def inhibit_command(why: str) -> list[str]:
    """Arma el comando de Linux que bloquea la suspensión mientras siga en marcha.

    Args:
        why (str): Motivo que muestra el sistema (por ejemplo, «Convirtiendo juegos»).

    Returns:
        list[str]: Argumentos para ``subprocess.Popen``.
    """
    return [_INHIBIT_TOOL, "--what=sleep:idle", f"--who={APP_TITLE}", f"--why={why}",
            "--mode=block", "sleep", "infinity"]


class SleepInhibitor:
    """Bloquea y libera la suspensión automática del equipo."""

    def __init__(self, platform: str = sys.platform,
                 which: Callable[[str], str | None] = shutil.which) -> None:
        """Prepara el bloqueo para el sistema actual.

        Args:
            platform (str): Valor de ``sys.platform``.
            which (Callable[[str], str | None]): Busca programas (los tests usan un doble).
        """
        self._platform, self._which = platform, which
        self._process: subprocess.Popen[bytes] | None = None
        self.active = False

    def acquire(self, why: str) -> bool:
        """Impide la suspensión (no hace nada si ya estaba bloqueada).

        Args:
            why (str): Motivo que muestra el sistema.

        Returns:
            bool: ``True`` si el sistema aceptó el bloqueo.
        """
        if self.active:
            return True
        if self._platform == "win32":
            self.active = _set_execution_state(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
        elif self._platform.startswith("linux") and self._which(_INHIBIT_TOOL):
            try:
                self._process = subprocess.Popen(
                    inhibit_command(why), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.active = True
            except OSError:
                self.active = False
        return self.active

    def release(self) -> None:
        """Vuelve a permitir la suspensión."""
        if not self.active:
            return
        if self._platform == "win32":
            _set_execution_state(_ES_CONTINUOUS)
        elif self._process is not None:
            self._process.terminate()
            self._process = None
        self.active = False


def _set_execution_state(flags: int) -> bool:
    """Llama a ``SetThreadExecutionState`` de Windows.

    Args:
        flags (int): Combinación de banderas ``ES_*``.

    Returns:
        bool: ``True`` si Windows aceptó el cambio.
    """
    try:
        import ctypes  # import diferido: solo existe la API en Windows

        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False
