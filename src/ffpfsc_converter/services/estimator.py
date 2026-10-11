"""Estimación del tamaño final del .ffpfsc sin convertir el juego completo.

Se toman bloques de 64 KiB al azar (ponderados por tamaño de archivo), se
comprimen con zlib-ng igual que MkPFS y los que no reducen se cuentan en
crudo. La razón obtenida se extrapola al tamaño total. Cada bloque se comprime
una sola vez y sirve para las dos estimaciones: la normal y la de «Rendimiento
en la PS5» (que deja en crudo los bloques que ganan menos del umbral).
"""
from __future__ import annotations

import bisect
import random
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from ffpfsc_converter.config import (
    ESTIMATE_SAMPLE_BLOCKS,
    ESTIMATE_SEED,
    PERFORMANCE_THRESHOLD_GAIN,
    PFS_OVERHEAD_BYTES,
    PFS_OVERHEAD_RATIO,
    PFSC_BLOCK_SIZE,
)
from ffpfsc_converter.domain.models import FileEntry, SizeEstimates

try:
    from zlib_ng import zlib_ng as _zlib
except ImportError:  # pragma: no cover - zlib-ng es dependencia, pero hay respaldo
    import zlib as _zlib


def estimate_sizes(
    files: Sequence[FileEntry],
    levels: Sequence[int],
    sample_blocks: int = ESTIMATE_SAMPLE_BLOCKS,
    seed: int = ESTIMATE_SEED,
) -> SizeEstimates:
    """Estima el tamaño final en bytes para cada nivel de compresión.

    Args:
        files (Sequence[FileEntry]): Archivos que forman el juego.
        levels (Sequence[int]): Niveles de compresión zlib a estimar.
        sample_blocks (int): Cantidad de bloques de 64 KiB a muestrear.
        seed (int): Semilla del muestreo; fija para resultados reproducibles.

    Returns:
        SizeEstimates: Nivel → bytes estimados (normal y con «Rendimiento en la PS5»),
        con la sobrecarga PFS incluida. Si no hay datos, ``0``; si no se pudo leer
        ningún bloque, el tamaño original.
    """
    total = sum(f.size for f in files)
    blocks = _read_blocks(files, _sample_offsets(files, sample_blocks, seed)) if total else []
    if not blocks:
        return SizeEstimates({lv: total for lv in levels}, {lv: total for lv in levels})
    with ThreadPoolExecutor(max_workers=len(levels)) as pool:
        ratios = dict(zip(levels, pool.map(lambda lv: _ratios(blocks, lv), levels),
                          strict=True))
    return SizeEstimates(
        standard={lv: _final_size(total, normal) for lv, (normal, _fast) in ratios.items()},
        performance={lv: _final_size(total, fast) for lv, (_normal, fast) in ratios.items()},
    )


def compression_ratio(blocks: Sequence[bytes], level: int, threshold_gain: int = 0) -> float:
    """Calcula la razón almacenado/original de una muestra de bloques.

    Un bloque que no se reduce al comprimirlo (o que gana menos que
    ``threshold_gain``) se cuenta en crudo, igual que hace PFSC.

    Args:
        blocks (Sequence[bytes]): Bloques de la muestra (no vacía).
        level (int): Nivel de compresión zlib.
        threshold_gain (int): Ganancia mínima (en %) para contar un bloque comprimido.

    Returns:
        float: Valor entre ``0`` y ``1``; ``1.0`` = sin ahorro.

    Raises:
        ZeroDivisionError: Si ``blocks`` está vacía.
    """
    stored = original = 0
    for block in blocks:
        stored += stored_block_size(len(block), len(_zlib.compress(block, level)), threshold_gain)
        original += len(block)
    return stored / original


def stored_block_size(raw: int, compressed: int, threshold_gain: int) -> int:
    """Calcula lo que ocupa un bloque en el ``.ffpfsc``, con la misma regla que MkPFS.

    Args:
        raw (int): Bytes del bloque sin comprimir (mayor que cero).
        compressed (int): Bytes del bloque comprimido.
        threshold_gain (int): Ganancia mínima (en %) para guardarlo comprimido.

    Returns:
        int: ``compressed`` si reduce el bloque y gana al menos el umbral; si no, ``raw``.
    """
    gain = (raw - compressed) * 100 / raw
    return compressed if compressed < raw and gain >= threshold_gain else raw


def _ratios(blocks: Sequence[bytes], level: int) -> tuple[float, float]:
    """Calcula la razón normal y la de «Rendimiento en la PS5» comprimiendo una sola vez.

    Args:
        blocks (Sequence[bytes]): Bloques de la muestra (no vacía).
        level (int): Nivel de compresión zlib.

    Returns:
        tuple[float, float]: Razón normal y razón con ``PERFORMANCE_THRESHOLD_GAIN``.
    """
    normal = fast = original = 0
    for block in blocks:
        packed = len(_zlib.compress(block, level))
        normal += stored_block_size(len(block), packed, 0)
        fast += stored_block_size(len(block), packed, PERFORMANCE_THRESHOLD_GAIN)
        original += len(block)
    return normal / original, fast / original


def _final_size(total: int, ratio: float) -> int:
    """Extrapola la razón de la muestra al juego completo, con la sobrecarga PFS.

    Args:
        total (int): Bytes del juego.
        ratio (float): Razón almacenado/original de la muestra.

    Returns:
        int: Bytes estimados del ``.ffpfsc``.
    """
    return int(total * ratio * PFS_OVERHEAD_RATIO) + PFS_OVERHEAD_BYTES


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
