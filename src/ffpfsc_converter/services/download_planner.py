"""Convierte un archivo o carpeta de la PS5 en la lista de archivos a descargar."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from ffpfsc_converter.config import PARTIAL_SUFFIX
from ffpfsc_converter.domain.remote import FileTransfer, RemoteEntry
from ffpfsc_converter.services.remote_client import RemoteClient

#: Caracteres que Windows no admite en nombres de archivo.
_INVALID_LOCAL_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


@dataclass
class DownloadPlan:
    """Lo que hay que crear y descargar para un elemento remoto.

    Attributes:
        directories (list[Path]): Carpetas locales a crear (incluidas las vacías).
        files (list[FileTransfer]): Archivos a descargar.
    """

    directories: list[Path] = field(default_factory=list)
    files: list[FileTransfer] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        """Calcula el tamaño total a descargar.

        Returns:
            int: Suma de los tamaños de todos los archivos.
        """
        return sum(f.size for f in self.files)


def local_name(name: str) -> str:
    """Adapta un nombre remoto para que sea válido en cualquier sistema.

    Args:
        name (str): Nombre del archivo o carpeta en la PS5.

    Returns:
        str: El mismo nombre con los caracteres inválidos en Windows cambiados
        por ``_`` y sin puntos ni espacios finales.
    """
    cleaned = _INVALID_LOCAL_CHARS.sub("_", name).rstrip(". ")
    return cleaned or "_"


def plan_download(client: RemoteClient, entry: RemoteEntry, destination: Path) -> DownloadPlan:
    """Calcula qué carpetas crear y qué archivos descargar.

    Args:
        client (RemoteClient): Cliente conectado, usado para recorrer carpetas.
        entry (RemoteEntry): Archivo o carpeta elegido en la PS5.
        destination (Path): Carpeta local donde se guarda.

    Returns:
        DownloadPlan: Carpetas y archivos con sus rutas locales.
    """
    root = destination / local_name(entry.name)
    if not entry.is_dir:
        return DownloadPlan(files=[FileTransfer(entry.path, root, entry.size)])
    plan = DownloadPlan(directories=[root])
    base = PurePosixPath(entry.path)
    for item in client.walk(entry.path):
        relative = PurePosixPath(item.path).relative_to(base)
        local = root.joinpath(*(local_name(part) for part in relative.parts))
        if item.is_dir:
            plan.directories.append(local)
        else:
            plan.files.append(FileTransfer(item.path, local, item.size))
    return plan


def partial_path(final: Path) -> Path:
    """Calcula la ruta del archivo a medio descargar.

    Args:
        final (Path): Ruta definitiva del archivo.

    Returns:
        Path: La misma ruta con el sufijo ``.part``.
    """
    return final.with_name(final.name + PARTIAL_SUFFIX)


def bytes_already_local(plan: DownloadPlan) -> int:
    """Cuenta los bytes que ya están en este equipo (completos o a medias).

    Args:
        plan (DownloadPlan): Plan de descarga.

    Returns:
        int: Bytes que no hará falta volver a descargar.
    """
    total = 0
    for transfer in plan.files:
        final, part = transfer.local_path, partial_path(transfer.local_path)
        if final.is_file() and final.stat().st_size == transfer.size:
            total += transfer.size
        elif part.is_file():
            total += min(part.stat().st_size, transfer.size)
    return total
