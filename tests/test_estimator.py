from __future__ import annotations

import os
from pathlib import Path

from ffpfsc_converter.config import PFS_OVERHEAD_BYTES
from ffpfsc_converter.domain.models import FileEntry
from ffpfsc_converter.services.estimator import compression_ratio, estimate_sizes


def _file(path: Path, data: bytes) -> FileEntry:
    """Escribe un archivo y devuelve su FileEntry."""
    path.write_bytes(data)
    return FileEntry(str(path), len(data))


def test_empty_input() -> None:
    """Sin archivos, la estimación es cero para cada nivel."""
    assert estimate_sizes([], [3, 9]) == {3: 0, 9: 0}


def test_zeros_compress_a_lot(tmp_path: Path) -> None:
    """Los datos repetitivos se estiman casi sin tamaño."""
    files = [_file(tmp_path / "z.bin", b"\x00" * (4 << 20))]
    est = estimate_sizes(files, [3, 9], sample_blocks=64)
    assert set(est) == {3, 9}
    assert all(PFS_OVERHEAD_BYTES <= size < PFS_OVERHEAD_BYTES + (1 << 20) for size in est.values())


def test_random_data_is_stored_raw(tmp_path: Path) -> None:
    """Los datos incompresibles nunca se estiman por debajo del original."""
    size = 2 << 20
    files = [_file(tmp_path / "r.bin", os.urandom(size))]
    est = estimate_sizes(files, [6], sample_blocks=32)
    assert est[6] >= size  # nunca menor que el original con datos incompresibles


def test_estimate_is_deterministic(tmp_path: Path) -> None:
    """La misma entrada produce siempre la misma estimación."""
    files = [_file(tmp_path / f"{i}.bin", os.urandom(200_000) + b"\x00" * 200_000)
             for i in range(3)]
    assert estimate_sizes(files, [3]) == estimate_sizes(files, [3])


def test_compression_ratio_caps_at_one() -> None:
    """Un bloque que crece al comprimirse se cuenta en crudo."""
    assert compression_ratio([os.urandom(65536)], 9) == 1.0
