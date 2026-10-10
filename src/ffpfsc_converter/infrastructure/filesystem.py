"""Utilidades del sistema de archivos."""
from __future__ import annotations

import contextlib
import os
import shutil
from pathlib import Path

from ffpfsc_converter.domain.models import FileEntry


def list_files(root: Path) -> list[FileEntry]:
    """Lista los archivos regulares no vacíos bajo ``root`` (sin seguir enlaces)."""
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
    """Archivos que forman el juego: la imagen misma o el contenido de la carpeta."""
    if game_root.is_file():
        return [FileEntry(str(game_root), game_root.stat().st_size)]
    return list_files(game_root)


def free_space(directory: Path) -> int:
    return shutil.disk_usage(directory).free


def remove_quietly(path: Path) -> None:
    """Borra ``path`` si existe, ignorando errores."""
    with contextlib.suppress(OSError):
        path.unlink(missing_ok=True)
