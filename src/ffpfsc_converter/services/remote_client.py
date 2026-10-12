"""Contrato del cliente remoto que usan los servicios del explorador.

Los servicios dependen de este ``Protocol`` y no de ``FtpClient``: así los
tests pueden usar un servidor FTP local o un doble sin red.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import BinaryIO, Protocol

from ffpfsc_converter.domain.remote import ConsoleTarget, RemoteEntry


class RemoteClient(Protocol):
    """Operaciones remotas que necesitan el explorador y las descargas."""

    def connect(self) -> None:
        """Abre la conexión con la consola."""
        ...

    def close(self) -> None:
        """Cierra la conexión."""
        ...

    def list_dir(self, path: str) -> list[RemoteEntry]:
        """Lista una carpeta remota.

        Args:
            path (str): Carpeta remota absoluta.

        Returns:
            list[RemoteEntry]: Contenido de la carpeta.
        """
        ...

    def walk(self, path: str) -> Iterator[RemoteEntry]:
        """Recorre una carpeta remota de forma recursiva.

        Args:
            path (str): Carpeta remota absoluta.

        Yields:
            RemoteEntry: Cada carpeta y archivo encontrado.
        """
        ...

    def download(
        self, remote_path: str, sink: BinaryIO, offset: int, on_chunk: Callable[[int], None]
    ) -> None:
        """Descarga un archivo remoto.

        Args:
            remote_path (str): Archivo remoto absoluto.
            sink (BinaryIO): Destino ya posicionado en ``offset``.
            offset (int): Bytes ya descargados.
            on_chunk (Callable[[int], None]): Se llama con el tamaño de cada bloque.
        """
        ...

    def upload(
        self, source: BinaryIO, remote_path: str, offset: int, on_chunk: Callable[[int], None]
    ) -> None:
        """Sube un archivo.

        Args:
            source (BinaryIO): Archivo local posicionado en ``offset``.
            remote_path (str): Ruta remota de destino.
            offset (int): Bytes que ya están en la consola.
            on_chunk (Callable[[int], None]): Se llama con el tamaño de cada bloque.
        """
        ...

    def size(self, remote_path: str) -> int | None:
        """Consulta el tamaño de un archivo remoto.

        Args:
            remote_path (str): Ruta remota.

        Returns:
            int | None: Tamaño, o ``None`` si no existe.
        """
        ...

    def rename(self, source: str, destination: str) -> None:
        """Renombra un archivo remoto.

        Args:
            source (str): Ruta actual.
            destination (str): Ruta nueva.
        """
        ...

    def make_dir(self, remote_path: str) -> None:
        """Crea una carpeta remota (si ya existe, no hace nada).

        Args:
            remote_path (str): Ruta de la carpeta.
        """
        ...


#: Crea un cliente para una consola (en la app, ``FtpClient``).
ClientFactory = Callable[[ConsoleTarget], RemoteClient]
