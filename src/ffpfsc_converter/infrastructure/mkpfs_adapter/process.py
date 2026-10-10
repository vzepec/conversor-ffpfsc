"""Ejecución del proceso ``mkpfs pack``."""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from collections.abc import Iterator

from ffpfsc_converter.infrastructure.mkpfs_adapter.output import split_lines

_READ_CHUNK = 4096


class PackProcess:
    """Proceso ``mkpfs pack`` en ejecución.

    Se lanza en su propia sesión para poder terminar también a sus procesos
    hijo (MkPFS usa varios procesos de compresión).
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
            start_new_session=True,
            bufsize=0,
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
        """Envía ``SIGTERM`` a todo el grupo de procesos si sigue en ejecución."""
        if self._proc.poll() is not None:
            return
        with contextlib.suppress(OSError):
            os.killpg(self._proc.pid, signal.SIGTERM)
