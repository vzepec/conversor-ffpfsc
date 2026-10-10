"""Excepciones propias de la aplicación.

Todas heredan de :class:`ConverterError`; su mensaje está pensado para
mostrarse directamente al usuario.
"""
from __future__ import annotations

from pathlib import Path


class ConverterError(Exception):
    """Error base del conversor."""


class SourceNotFoundError(ConverterError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"No existe:\n{path}")
        self.path = path


class UnsupportedFormatError(ConverterError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            f"Formato no soportado:\n{path}\n\n"
            "Usa una carpeta de juego o un archivo .exfat / .ffpkg."
        )
        self.path = path


class GameNotFoundError(ConverterError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            f"No encontré un juego dentro de:\n{path}\n\n"
            "Arrastra la carpeta del juego (con eboot.bin y sce_sys) "
            "o un archivo .exfat / .ffpkg."
        )
        self.path = path
