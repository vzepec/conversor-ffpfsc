"""Estimación del tamaño final del .ffpfsc sin convertir el juego completo.

Se toman bloques de 64 KiB al azar (ponderados por tamaño de archivo), se
comprimen con zlib-ng igual que MkPFS y los que no reducen se cuentan en
crudo. La razón obtenida se extrapola al tamaño total.
"""
from __future__ import annotations

import bisect
import random
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from ffpfsc_converter.config import (
    ESTIMATE_SAMPLE_BLOCKS,
    ESTIMATE_SEED,
    PFS_OVERHEAD_BYTES,
    PFS_OVERHEAD_RATIO,
    PFSC_BLOCK_SIZE,
)
from ffpfsc_converter.domain.models import FileEntry

try:
    from zlib_ng import zlib_ng as _zlib
except ImportError:  # pragma: no cover - zlib-ng es dependencia, pero hay respaldo
    import zlib as _zlib


def estimate_sizes(
    files: Sequence[FileEntry],
    levels: Sequence[int],
    sample_blocks: int = ESTIMATE_SAMPLE_BLOCKS,
    seed: int = ESTIMATE_SEED,
) -> dict[int, int]:
    """Estima el tamaño final en bytes para cada nivel de compresión.

    Args:
        files (Sequence[FileEntry]): Archivos que forman el juego.
        levels (Sequence[int]): Niveles de compresión zlib a estimar.
        sample_blocks (int): Cantidad de bloques de 64 KiB a muestrear.
        seed (int): Semilla del muestreo; fija para resultados reproducibles.

    Returns:
        dict[int, int]: Nivel → bytes estimados, con la sobrecarga PFS incluida.
        Si no hay datos devuelve ``0``; si no se pudo leer ningún bloque, el
        tamaño original.
    """
    total = sum(f.size for f in files)
    if total == 0:
        return {level: 0 for level in levels}
    blocks = _read_blocks(files, _sample_offsets(files, sample_blocks, seed))
    if not blocks:
        return {level: total for level in levels}
    with ThreadPoolExecutor(max_workers=len(levels)) as pool:
        results = pool.map(lambda lv: compression_ratio(blocks, lv), levels)
        ratios = dict(zip(levels, results, strict=True))
    return {
        level: int(total * ratio * PFS_OVERHEAD_RATIO) + PFS_OVERHEAD_BYTES
        for level, ratio in ratios.items()
    }


def compression_ratio(blocks: Sequence[bytes], level: int) -> float:
    """Calcula la razón almacenado/original de una muestra de bloques.

    Un bloque que no se reduce al comprimirlo se cuenta en crudo, igual que
    hace PFSC.

    Args:
        blocks (Sequence[bytes]): Bloques de la muestra (no vacía).
        level (int): Nivel de compresión zlib.

    Returns:
        float: Valor entre ``0`` y ``1``; ``1.0`` = sin ahorro.

    Raises:
        ZeroDivisionError: Si ``blocks`` está vacía.
    """
    stored = original = 0
    for block in blocks:
        stored += min(len(_zlib.compress(block, level)), len(block))
        original += len(block)
    return stored / original


def _sample_offsets(
    files: Sequence[FileEntry], count: int, seed: int
) -> dict[int, list[int]]:
    """Elige offsets alineados a bloque, ponderados por tamaño de archivo.

    Args:
        files (Sequence[FileEntry]): Archivos del juego (tamaño total > 0).
        count (int): Cantidad de offsets a elegir.
        seed (int): Semilla del generador aleatorio.

    Returns:
        dict[int, list[int]]: Índice de archivo → offsets elegidos en ese archivo.
    """
    rng = random.Random(seed)
    cumulative: list[int] = []
    acc = 0
    for f in files:
        acc += f.size
        cumulative.append(acc)
    picks: dict[int, list[int]] = {}
    for _ in range(count):
        x = rng.randrange(acc)
        i = bisect.bisect_right(cumulative, x)
        start = cumulative[i - 1] if i else 0
        offset = (x - start) // PFSC_BLOCK_SIZE * PFSC_BLOCK_SIZE
        picks.setdefault(i, []).append(offset)
    return picks


def _read_blocks(files: Sequence[FileEntry], picks: dict[int, list[int]]) -> list[bytes]:
    """Lee del disco los bloques elegidos, en orden para minimizar saltos.

    Args:
        files (Sequence[FileEntry]): Archivos del juego.
        picks (dict[int, list[int]]): Índice de archivo → offsets a leer.

    Returns:
        list[bytes]: Bloques leídos; los archivos ilegibles se omiten.
    """
    blocks: list[bytes] = []
    for i in sorted(picks):
        try:
            with open(files[i].path, "rb") as fh:
                for offset in sorted(picks[i]):
                    fh.seek(offset)
                    data = fh.read(PFSC_BLOCK_SIZE)
                    if data:
                        blocks.append(data)
        except OSError:
            continue
    return blocks
