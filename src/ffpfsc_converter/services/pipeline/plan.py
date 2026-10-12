"""Decisiones puras del pipeline: qué se puede convertir, nombres y estrategia de espacio."""
from __future__ import annotations

import posixpath
from collections.abc import Iterable
from pathlib import PurePosixPath

from ffpfsc_converter.config import IMAGE_EXTENSIONS, OUTPUT_EXTENSION
from ffpfsc_converter.domain.models import OutputFormat
from ffpfsc_converter.domain.pipeline import ReplacePlan, SpaceStrategy
from ffpfsc_converter.domain.remote import RemoteEntry
from ffpfsc_converter.infrastructure.ftp import join_remote
from ffpfsc_converter.services.remote_upload import part_path


def can_use_lz4(entry: RemoteEntry) -> bool:
    """Indica si un elemento de la PS5 se puede reemplazar por una carpeta LZ4.

    Args:
        entry (RemoteEntry): Elemento remoto.

    Returns:
        bool: ``True`` solo para carpetas (una imagen no se puede revisar por dentro).
    """
    return entry.is_dir


def is_convertible(entry: RemoteEntry) -> bool:
    """Indica si un elemento de la PS5 se puede comprimir y reemplazar.

    Args:
        entry (RemoteEntry): Elemento remoto.

    Returns:
        bool: ``True`` para carpetas (salvo las ya comprimidas en LZ4) y para imágenes
        ``.exfat``/``.ffpkg``.
    """
    if entry.is_lz4:
        return False
    return entry.is_dir or PurePosixPath(entry.name).suffix.lower() in IMAGE_EXTENSIONS


def build_replace_plan(entry: RemoteEntry, siblings: Iterable[str],
                       output_format: OutputFormat = OutputFormat.FFPFSC) -> ReplacePlan:
    """Calcula dónde se subirá el juego comprimido que reemplaza a un elemento.

    Un ``.ffpfsc`` queda en la misma carpeta que el original, con su nombre (sin
    extensión, si era una imagen). Una carpeta LZ4 ocupa el lugar del original con el
    mismo nombre, así las rutas que ya usaba la PS5 siguen sirviendo.

    Args:
        entry (RemoteEntry): Carpeta o imagen original.
        siblings (Iterable[str]): Nombres que hay en la misma carpeta remota.
        output_format (OutputFormat): ``.ffpfsc`` o LZ4 (solo para carpetas).

    Returns:
        ReplacePlan: Rutas definitiva y temporal, y si el nombre ya está ocupado.
    """
    if output_format is OutputFormat.LZ4:
        return ReplacePlan(entry, entry.path, part_path(entry.path), False)
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
        upload_size (int): Bytes a subir.
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
