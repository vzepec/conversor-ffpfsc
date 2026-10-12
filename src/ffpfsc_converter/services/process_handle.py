"""Contrato de un proceso externo (MkPFS o las herramientas de ampr_emu) para los runners."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Protocol


class ProcessHandle(Protocol):
    """Contrato mínimo que el runner necesita de un proceso de empaquetado."""

    def lines(self) -> Iterator[str]:
        """Lee la salida del proceso línea a línea hasta que termina.

        Yields:
            str: Cada línea no vacía de la salida.
        """
        ...

    def wait(self) -> int:
        """Espera a que el proceso termine.

        Returns:
            int: Código de salida (``0`` = éxito).
        """
        ...

    def terminate(self) -> None:
        """Termina el proceso si sigue en ejecución."""
        ...


ProcessFactory = Callable[[list[str]], ProcessHandle]
