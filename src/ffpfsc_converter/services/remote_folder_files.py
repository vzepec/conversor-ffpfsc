"""Piezas de la subida de carpetas: qué archivos, qué subcarpetas y cómo se informa."""
from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ffpfsc_converter.services.remote_upload import ProgressCallback
from ffpfsc_converter.services.retry import RetryCallback


@dataclass(frozen=True)
class FolderFile:
    """Archivo de la carpeta que se sube.

    Attributes:
        local (Path): Archivo en este equipo.
        relative (str): Ruta dentro de la carpeta, con ``/``.
        size (int): Bytes.
    """

    local: Path
    relative: str
    size: int


def folder_files(folder: Path) -> list[FolderFile]:
    """Lista los archivos de una carpeta (sin seguir enlaces simbólicos), en orden.

    Args:
        folder (Path): Carpeta local.

    Returns:
        list[FolderFile]: Archivos con su ruta relativa y tamaño.
    """
    found: list[FolderFile] = []
    for dirpath, _dirs, names in os.walk(folder):
        for name in names:
            path = Path(dirpath, name)
            if path.is_file() and not path.is_symlink():
                found.append(FolderFile(path, path.relative_to(folder).as_posix(),
                                        path.stat().st_size))
    return sorted(found, key=lambda f: f.relative)


def remote_dirs(files: Sequence[FolderFile]) -> list[str]:
    """Calcula las subcarpetas que hay que crear, de las más externas a las internas.

    Args:
        files (Sequence[FolderFile]): Archivos de la carpeta.

    Returns:
        list[str]: Rutas relativas de carpetas (sin la raíz).
    """
    dirs = {str(parent) for f in files for parent in PurePosixPath(f.relative).parents}
    dirs.discard(".")
    return sorted(dirs, key=lambda d: (d.count("/"), d))


@dataclass(frozen=True)
class UploadHooks:
    """Cómo informa y se controla una subida.

    Attributes:
        progress (ProgressCallback): Avance (hecho, total, velocidad, segundos restantes).
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.
        on_retry (RetryCallback): Se llama antes de cada reintento.
    """

    progress: ProgressCallback
    should_cancel: Callable[[], bool]
    on_retry: RetryCallback


def offset_hooks(hooks: UploadHooks, done: int, total: int) -> UploadHooks:
    """Adapta el avance de un archivo al de la carpeta completa.

    Args:
        hooks (UploadHooks): Avance de la carpeta.
        done (int): Bytes de los archivos ya subidos.
        total (int): Bytes de toda la carpeta.

    Returns:
        UploadHooks: Los mismos controles con el avance desplazado.
    """
    def progress(file_done: int, _file_total: int, speed: float, _eta: float | None) -> None:
        """Informa el avance total con su tiempo restante.

        Args:
            file_done (int): Bytes subidos del archivo actual.
            _file_total (int): Tamaño del archivo actual (no se usa).
            speed (float): Velocidad en bytes por segundo.
            _eta (float | None): Restante del archivo (se recalcula para la carpeta).
        """
        current = done + file_done
        eta = (total - current) / speed if speed > 0 else None
        hooks.progress(current, total, speed, eta)

    return UploadHooks(progress, hooks.should_cancel, hooks.on_retry)
