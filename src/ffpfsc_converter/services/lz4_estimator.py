"""Estimación del peso de la carpeta LZ4 (formato AMPR) sin convertir el juego.

Los archivos que el perfil genérico deja sueltos cuentan completos; de los que se
comprimen se leen bloques de 64 KiB al azar (ponderados por tamaño) y se comprimen
con LZ4 HC, igual que ``ampr_pack.py``. La razón se extrapola a su tamaño total.
"""
from __future__ import annotations

import random
from collections.abc import Sequence
from pathlib import Path

import lz4.block

from ffpfsc_converter.config import (
    ESTIMATE_SEED,
    LZ4_ESTIMATE_LEVEL,
    LZ4_ESTIMATE_SAMPLE_BLOCKS,
    PFSC_BLOCK_SIZE,
)
from ffpfsc_converter.domain.models import FileEntry
from ffpfsc_converter.services.ampr_profile import AmprAction, classify


def estimate_lz4(files: Sequence[FileEntry], root: Path,
                 sample_blocks: int = LZ4_ESTIMATE_SAMPLE_BLOCKS) -> int:
    """Estima los bytes de la carpeta LZ4 de un juego.

    Args:
        files (Sequence[FileEntry]): Archivos del juego (rutas absolutas).
        root (Path): Carpeta del juego, para clasificar cada archivo.
        sample_blocks (int): Bloques a muestrear entre los que se comprimen.

    Returns:
        int: Bytes estimados (sueltos completos + comprimidos según la muestra).
    """
    packed = [f for f in files if classify(_relative(f, root)) is not AmprAction.LOOSE]
    loose = sum(f.size for f in files) - sum(f.size for f in packed)
    packed_total = sum(f.size for f in packed)
    if packed_total == 0:
        return loose
    return loose + int(packed_total * _sample_ratio(packed, sample_blocks))


def block_ratio(blocks: Sequence[bytes], level: int = LZ4_ESTIMATE_LEVEL) -> float:
    """Calcula la razón comprimido/original de una muestra (un bloque que crece cuenta crudo).

    Args:
        blocks (Sequence[bytes]): Bloques leídos (no vacía).
        level (int): Nivel LZ4 HC.

    Returns:
        float: Entre ``0`` y ``1``.

    Raises:
        ZeroDivisionError: Si ``blocks`` está vacía.
    """
    stored = sum(min(len(lz4.block.compress(b, mode="high_compression", compression=level,
                                            store_size=False)), len(b)) for b in blocks)
    return stored / sum(len(b) for b in blocks)


def _sample_ratio(files: Sequence[FileEntry], count: int) -> float:
    """Lee bloques al azar de los archivos (ponderados por tamaño) y mide su razón.

    Args:
        files (Sequence[FileEntry]): Archivos que se comprimen (tamaño total > 0).
        count (int): Bloques a leer.

    Returns:
        float: Razón de la muestra; ``1.0`` si no se pudo leer nada.
    """
    rng = random.Random(ESTIMATE_SEED)
    chosen = rng.choices(files, weights=[f.size for f in files], k=count)
    blocks: list[bytes] = []
    for entry in chosen:
        offset = rng.randrange(max(entry.size, 1)) // PFSC_BLOCK_SIZE * PFSC_BLOCK_SIZE
        try:
            with open(entry.path, "rb") as fh:
                fh.seek(offset)
                if data := fh.read(PFSC_BLOCK_SIZE):
                    blocks.append(data)
        except OSError:
            continue
    return block_ratio(blocks) if blocks else 1.0


def _relative(entry: FileEntry, root: Path) -> str:
    """Convierte la ruta de un archivo en relativa a la carpeta del juego, con ``/``.

    Args:
        entry (FileEntry): Archivo.
        root (Path): Carpeta del juego.

    Returns:
        str: Ruta relativa (o el nombre si está fuera de la carpeta).
    """
    path = Path(entry.path)
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
