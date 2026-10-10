"""Decisiones puras del pipeline: qué se puede convertir, nombres y estrategia de espacio."""
from __future__ import annotations

import posixpath
from collections.abc import Iterable
from pathlib import PurePosixPath

from ffpfsc_converter.config import IMAGE_EXTENSIONS, OUTPUT_EXTENSION
from ffpfsc_converter.domain.pipeline import ReplacePlan, SpaceStrategy
from ffpfsc_converter.domain.remote import RemoteEntry
from ffpfsc_converter.infrastructure.ftp import join_remote
from ffpfsc_converter.services.remote_upload import part_path


def is_convertible(entry: RemoteEntry) -> bool:
    """Indica si un elemento de la PS5 se puede comprimir a ``.ffpfsc``.

    Args:
        entry (RemoteEntry): Elemento remoto.

    Returns:
        bool: ``True`` para carpetas y para imágenes ``.exfat``/``.ffpkg``.
    """
    return entry.is_dir or PurePosixPath(entry.name).suffix.lower() in IMAGE_EXTENSIONS


def build_replace_plan(entry: RemoteEntry, siblings: Iterable[str]) -> ReplacePlan:
    """Calcula dónde se subirá el ``.ffpfsc`` que reemplaza a un elemento.

    El archivo nuevo queda en la misma carpeta que el original, con su nombre
    (sin extensión, si era una imagen) y extensión ``.ffpfsc``.

    Args:
        entry (RemoteEntry): Carpeta o imagen original.
        siblings (Iterable[str]): Nombres que hay en la misma carpeta remota.

    Returns:
        ReplacePlan: Rutas definitiva y temporal, y si el nombre ya está ocupado.
    """
    base = entry.name if entry.is_dir else PurePosixPath(entry.name).stem
    final_name = base + OUTPUT_EXTENSION
    final = join_remote(posixpath.dirname(entry.path) or "/", final_name)
    return ReplacePlan(entry, final, part_path(final), final_name in set(siblings))


def choose_strategy(
    usable: int, upload_size: int, already_uploaded: int, original_size: int
) -> SpaceStrategy:
    """Elige el orden de reemplazo según el espacio libre de la PS5.

    Args:
        usable (int): Bytes que se pueden escribir en el disco de destino.
        upload_size (int): Tamaño del ``.ffpfsc``.
        already_uploaded (int): Bytes de una subida anterior que se reanudará.
        original_size (int): Lo que libera borrar el original.

    Returns:
        SpaceStrategy: ``UPLOAD_FIRST`` si caben ambos; ``DELETE_FIRST`` si solo cabe
        tras borrar el original; ``INSUFFICIENT`` si no cabe de ninguna forma.
    """
    needed = max(0, upload_size - already_uploaded)
    if usable >= needed:
        return SpaceStrategy.UPLOAD_FIRST
    if usable + original_size >= needed:
        return SpaceStrategy.DELETE_FIRST
    return SpaceStrategy.INSUFFICIENT
