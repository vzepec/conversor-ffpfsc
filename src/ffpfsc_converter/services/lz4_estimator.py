"""Estimación del peso de la carpeta LZ4 (formato AMPR) sin convertir el juego.

Los archivos que el perfil genérico deja sueltos cuentan completos; de los que se
comprimen se leen bloques de 64 KiB al azar (ponderados por tamaño), se comprimen
con el nivel LZ4 de cada modo (rápido o HC: el rápido comprime menos) y se ubican
en páginas de 64 KiB con las mismas reglas que ``ampr_pack.py`` (un bloque que
comprime poco va crudo; los comprimidos no cruzan páginas), porque eso decide el
peso real. La razón se extrapola a su tamaño total.
"""
from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import lz4.block

from ffpfsc_converter.config import (
    AMPR_CHUNK_ALIGN_BYTES,
    AMPR_IO_PAGE_BYTES,
    AMPR_MIN_SAVINGS_BYTES,
    AMPR_MIN_SAVINGS_RATIO,
    ESTIMATE_SEED,
    LZ4_ESTIMATE_SAMPLE_BLOCKS,
    LZ4_FAST_MAX_LEVEL,
    PFSC_BLOCK_SIZE,
)
from ffpfsc_converter.domain.models import FileEntry
from ffpfsc_converter.services.ampr_profile import AmprAction, classify


@dataclass(frozen=True)
class Lz4SizeEstimate:
    """Peso estimado de la carpeta LZ4.

    Attributes:
        totals (dict[int, int]): Bytes de la carpeta (sueltos completos + paquetes) por
            nivel LZ4.
        loose (int): Bytes que quedan sin empaquetar.
    """

    totals: dict[int, int]
    loose: int


def estimate_lz4(files: Sequence[FileEntry], root: Path, levels: Iterable[int],
                 sample_blocks: int = LZ4_ESTIMATE_SAMPLE_BLOCKS) -> Lz4SizeEstimate:
    """Estima los bytes de la carpeta LZ4 de un juego para cada nivel.

    Los bloques se leen una sola vez y se comprimen con cada nivel.

    Args:
        files (Sequence[FileEntry]): Archivos del juego (rutas absolutas).
        root (Path): Carpeta del juego, para clasificar cada archivo.
        levels (Iterable[int]): Niveles LZ4 a estimar.
        sample_blocks (int): Bloques a muestrear entre los que se comprimen.

    Returns:
        Lz4SizeEstimate: Total estimado por nivel y la parte que queda suelta.
    """
    packed = [f for f in files if classify(_relative(f, root)) is not AmprAction.LOOSE]
    packed_total = sum(f.size for f in packed)
    loose = sum(f.size for f in files) - packed_total
    blocks = _sample_blocks(packed, sample_blocks) if packed_total else []
    return Lz4SizeEstimate({level: loose + int(packed_total * (block_ratio(blocks, level)
                                                               if blocks else 1.0))
                            for level in levels}, loose)


def block_ratio(blocks: Sequence[bytes], level: int) -> float:
    """Calcula cuánto ocuparía una muestra en los paquetes, contando páginas y bloques crudos.

    Args:
        blocks (Sequence[bytes]): Bloques leídos (no vacía).
        level (int): Nivel LZ4 (hasta ``LZ4_FAST_MAX_LEVEL`` es el modo rápido; luego HC).

    Returns:
        float: Bytes ocupados / bytes originales (puede pasar apenas de ``1`` por el relleno).

    Raises:
        ZeroDivisionError: Si ``blocks`` está vacía.
    """
    sizes = [stored_size(len(b), len(_compress(b, level))) for b in blocks]
    return packed_end(sizes) / sum(len(b) for b in blocks)


def _compress(block: bytes, level: int) -> bytes:
    """Comprime un bloque como ``ampr_pack``: modo rápido o HC según el nivel.

    Args:
        block (bytes): Bloque original.
        level (int): Nivel LZ4.

    Returns:
        bytes: Bloque comprimido (sin cabecera de tamaño).
    """
    if level <= LZ4_FAST_MAX_LEVEL:
        return lz4.block.compress(block, mode="default", store_size=False)
    return lz4.block.compress(block, mode="high_compression", compression=level,
                              store_size=False)


def stored_size(raw: int, compressed: int) -> int:
    """Decide si ``ampr_pack`` guarda un bloque comprimido o crudo.

    Args:
        raw (int): Bytes del bloque original.
        compressed (int): Bytes del bloque comprimido.

    Returns:
        int: ``compressed`` si ahorra lo suficiente; si no, ``raw``.
    """
    saved = raw - compressed
    pages_saved = -(-compressed // AMPR_IO_PAGE_BYTES) < -(-raw // AMPR_IO_PAGE_BYTES)
    need_bytes = 0 if pages_saved else AMPR_MIN_SAVINGS_BYTES
    need_ratio = 0.0 if pages_saved else AMPR_MIN_SAVINGS_RATIO
    return compressed if saved >= need_bytes and saved >= raw * need_ratio and saved > 0 \
        else raw


def packed_end(sizes: Sequence[int]) -> int:
    """Ubica los bloques uno tras otro como ``ampr_pack`` y devuelve dónde termina el último.

    Args:
        sizes (Sequence[int]): Bytes guardados de cada bloque, en orden.

    Returns:
        int: Bytes que ocupa el paquete.
    """
    page, align, position = AMPR_IO_PAGE_BYTES, AMPR_CHUNK_ALIGN_BYTES, 0
    for size in sizes:
        if size >= page:
            position = -(-position // page) * page
        else:
            position = -(-position // align) * align
            if position + size > -(-(position + 1) // page) * page:
                position = -(-position // page) * page
        position += size
    return position


def _sample_blocks(files: Sequence[FileEntry], count: int) -> list[bytes]:
    """Lee bloques al azar de los archivos (ponderados por tamaño).

    Args:
        files (Sequence[FileEntry]): Archivos que se comprimen (tamaño total > 0).
        count (int): Bloques a leer.

    Returns:
        list[bytes]: Bloques leídos (vacía si no se pudo leer nada).
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
    return blocks


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
