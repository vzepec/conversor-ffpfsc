"""Utilidades del sistema de archivos."""
from __future__ import annotations

import contextlib
import os
import shutil
from pathlib import Path

from ffpfsc_converter.domain.models import FileEntry


def list_files(root: Path) -> list[FileEntry]:
    """Lista los archivos regulares no vacíos bajo una carpeta, sin seguir enlaces.

    Args:
        root (Path): Carpeta que se recorre de forma recursiva.

    Returns:
        list[FileEntry]: Ruta y tamaño de cada archivo; los ilegibles se omiten.
    """
    entries: list[FileEntry] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if st.st_size > 0 and not os.path.islink(path):
                entries.append(FileEntry(path, st.st_size))
    return entries


def collect_game_files(game_root: Path) -> list[FileEntry]:
    """Obtiene los archivos que forman un juego.

    Args:
        game_root (Path): Imagen del juego o carpeta con ``eboot.bin``.

    Returns:
        list[FileEntry]: La imagen misma, o todos los archivos de la carpeta.

    Raises:
        OSError: Si ``game_root`` es un archivo y no se puede consultar su tamaño.
    """
    if game_root.is_file():
        return [FileEntry(str(game_root), game_root.stat().st_size)]
    return list_files(game_root)


def free_space(directory: Path) -> int:
    """Consulta el espacio libre del disco que contiene una carpeta.

    Args:
        directory (Path): Carpeta existente en el disco a consultar.

    Returns:
        int: Bytes libres.

    Raises:
        OSError: Si la carpeta no existe o no se puede consultar.
    """
    return shutil.disk_usage(directory).free


def remove_quietly(path: Path) -> None:
    """Borra un archivo si existe, ignorando cualquier error del sistema.

    Args:
        path (Path): Archivo a borrar.
    """
    with contextlib.suppress(OSError):
        path.unlink(missing_ok=True)


def remove_path(path: Path) -> None:
    """Borra un archivo o una carpeta completa de este equipo, ignorando errores.

    Args:
        path (Path): Archivo o carpeta local.
    """
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        remove_quietly(path)
