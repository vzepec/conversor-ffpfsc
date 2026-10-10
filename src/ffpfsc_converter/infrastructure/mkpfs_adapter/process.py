"""Ejecución del proceso ``mkpfs pack`` en Linux, macOS y Windows."""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from collections.abc import Iterator
from typing import Any

from ffpfsc_converter.infrastructure.mkpfs_adapter.output import split_lines

_READ_CHUNK = 4096
_IS_WINDOWS = os.name == "nt"
# Constantes de la API de Windows; se definen aquí porque ``subprocess`` solo
# las expone al ejecutarse en Windows.
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000


def popen_options(is_windows: bool = _IS_WINDOWS) -> dict[str, Any]:
    """Obtiene las opciones de ``Popen`` para aislar a MkPFS en su propio grupo.

    Así se puede terminar a MkPFS junto con sus procesos de compresión. En
    Windows, además, se evita que se abra una ventana de consola.

    Args:
        is_windows (bool): ``True`` para generar las opciones de Windows.

    Returns:
        dict[str, Any]: Argumentos adicionales para ``subprocess.Popen``.
    """
    if is_windows:
        return {"creationflags": _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW}
    return {"start_new_session": True}


def kill_tree_command(pid: int) -> list[str]:
    """Construye el comando de Windows que termina un proceso y todos sus hijos.

    Args:
        pid (int): Identificador del proceso principal.

    Returns:
        list[str]: Comando ``taskkill`` listo para ``subprocess.run``.
    """
    return ["taskkill", "/PID", str(pid), "/T", "/F"]


class PackProcess:
    """Proceso ``mkpfs pack`` en ejecución.

    Se lanza en su propio grupo de procesos para poder terminar también a sus
    procesos hijo (MkPFS usa varios procesos de compresión).
    """

    def __init__(self, command: list[str]) -> None:
        """Lanza el proceso con la salida estándar y de error unificadas.

        Args:
            command (list[str]): Línea de comandos de ``build_pack_command``.

        Raises:
            OSError: Si el ejecutable no existe o no se puede lanzar.
        """
        self._proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            **popen_options(),
        )

    def lines(self) -> Iterator[str]:
        """Lee la salida del proceso línea a línea hasta que termina.

        Yields:
            str: Cada línea no vacía emitida por MkPFS.
        """
        stdout = self._proc.stdout
        assert stdout is not None
        yield from split_lines(iter(lambda: stdout.read(_READ_CHUNK), b""))

    def wait(self) -> int:
        """Espera a que el proceso termine.

        Returns:
            int: Código de salida de MkPFS (``0`` = éxito).
        """
        return self._proc.wait()

    def terminate(self) -> None:
        """Termina el proceso y sus hijos si sigue en ejecución.

        Usa ``taskkill /T`` en Windows y ``SIGTERM`` al grupo en Linux y macOS.
        """
        if self._proc.poll() is not None:
            return
        with contextlib.suppress(OSError):
            if _IS_WINDOWS:
                subprocess.run(kill_tree_command(self._proc.pid), check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=_CREATE_NO_WINDOW)
            else:
                os.killpg(self._proc.pid, signal.SIGTERM)
