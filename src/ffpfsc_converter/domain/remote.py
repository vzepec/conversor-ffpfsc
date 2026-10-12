"""Modelos del explorador de archivos de la PS5."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class ConsoleTarget:
    """Datos para conectarse al servidor FTP de la PS5.

    Attributes:
        host (str): IP o nombre de la PS5 en la red local.
        port (int): Puerto FTP (2122 para ps5upload, 2121 para ftpsrv).
        user (str): Usuario; vacío si el servidor no pide credenciales.
        password (str): Contraseña; vacía si el servidor no la pide.
    """

    host: str
    port: int
    user: str = ""
    password: str = ""


@dataclass(frozen=True)
class RemoteEntry:
    """Archivo o carpeta de la PS5.

    Attributes:
        name (str): Nombre sin ruta.
        path (str): Ruta absoluta POSIX en la PS5.
        is_dir (bool): ``True`` si es una carpeta.
        size (int): Tamaño en bytes (``0`` en carpetas).
        modified (str): Fecha de modificación ``AAAAMMDDhhmmss``; vacía si se desconoce.
        is_lz4 (bool): ``True`` si es una carpeta de juego ya comprimida en LZ4 (se sabe
            tras revisarla por dentro).
    """

    name: str
    path: str
    is_dir: bool
    size: int = 0
    modified: str = ""
    is_lz4: bool = False


@dataclass(frozen=True)
class FileTransfer:
    """Archivo concreto a descargar.

    Attributes:
        remote_path (str): Ruta del archivo en la PS5.
        local_path (Path): Ruta final en este equipo.
        size (int): Tamaño esperado en bytes.
    """

    remote_path: str
    local_path: Path
    size: int


class DownloadState(Enum):
    """Estado de una descarga en la cola."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadJob:
    """Archivo o carpeta de la PS5 que el usuario pidió descargar.

    Attributes:
        entry (RemoteEntry): Elemento remoto elegido.
        destination (Path): Carpeta local donde se guarda.
        state (DownloadState): Estado actual en la cola.
        total_bytes (int): Bytes a descargar (se conoce al recorrer la carpeta).
        done_bytes (int): Bytes ya descargados, incluidos los reanudados.
        id (str): Identificador único, usado también como fila de la tabla.
        files (list[FileTransfer]): Archivos descargados (para verificarlos después).
    """

    entry: RemoteEntry
    destination: Path
    state: DownloadState = DownloadState.QUEUED
    total_bytes: int = 0
    done_bytes: int = 0
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    files: list[FileTransfer] = field(default_factory=list)

    @property
    def local_path(self) -> Path:
        """Calcula dónde quedará el archivo o la carpeta descargada.

        Returns:
            Path: ``destination`` más el nombre del elemento remoto.
        """
        return self.destination / self.entry.name


@dataclass(frozen=True)
class DownloadResult:
    """Resultado de una descarga.

    Attributes:
        succeeded (bool): ``True`` si todos los archivos se descargaron y verificaron.
        cancelled (bool): ``True`` si el usuario la canceló.
        elapsed_seconds (float): Duración de la descarga.
        files (int): Archivos descargados u omitidos por estar ya completos.
        message (str): Detalle del error, si lo hubo.
    """

    succeeded: bool
    cancelled: bool
    elapsed_seconds: float
    files: int = 0
    message: str = ""


@dataclass(frozen=True)
class StorageVolume:
    """Unidad de almacenamiento montada en la PS5.

    Attributes:
        path (str): Punto de montaje (``/data``, ``/mnt/usb0``, ``/mnt/ext0``…).
        device (str): Dispositivo que la respalda (``/dev/nvme…`` = M.2, ``/dev/da…`` = USB).
        total_bytes (int): Capacidad de la unidad.
        free_bytes (int): Espacio libre que puede usar una escritura normal.
    """

    path: str
    device: str
    total_bytes: int
    free_bytes: int
