"""Excepciones propias de la aplicación.

Todas heredan de :class:`ConverterError`; su mensaje está pensado para
mostrarse directamente al usuario.
"""
from __future__ import annotations

from pathlib import Path


class ConverterError(Exception):
    """Error base del conversor; su mensaje se muestra tal cual al usuario."""


class SourceNotFoundError(ConverterError):
    """La ruta agregada no existe.

    Attributes:
        path (Path): Ruta que no se encontró.
    """

    def __init__(self, path: Path) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            path (Path): Ruta que no se encontró.
        """
        super().__init__(f"No existe:\n{path}")
        self.path = path


class UnsupportedFormatError(ConverterError):
    """La ruta agregada es un archivo que no es una imagen soportada.

    Attributes:
        path (Path): Archivo rechazado.
    """

    def __init__(self, path: Path) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            path (Path): Archivo rechazado.
        """
        super().__init__(
            f"Formato no soportado:\n{path}\n\n"
            "Usa una carpeta de juego o un archivo .exfat / .ffpkg."
        )
        self.path = path


class GameNotFoundError(ConverterError):
    """La carpeta agregada no contiene un juego reconocible.

    Attributes:
        path (Path): Carpeta en la que se buscó.
    """

    def __init__(self, path: Path) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            path (Path): Carpeta en la que se buscó.
        """
        super().__init__(
            f"No encontré un juego dentro de:\n{path}\n\n"
            "Arrastra la carpeta del juego (con eboot.bin y sce_sys) "
            "o un archivo .exfat / .ffpkg."
        )
        self.path = path


class TransientError(ConverterError):
    """Error que puede resolverse reintentando (por ejemplo, una transferencia incompleta)."""


class RemoteConnectionError(ConverterError):
    """Falló la comunicación con la PS5; el mensaje explica qué revisar."""


class DownloadCancelledError(ConverterError):
    """El usuario canceló la descarga en curso."""

    def __init__(self) -> None:
        """Crea el error con un mensaje para el usuario."""
        super().__init__("Descarga cancelada")
