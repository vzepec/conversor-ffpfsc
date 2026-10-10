from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from conftest import FakeConsole
from ffpfsc_converter.errors import DownloadCancelledError
from ffpfsc_converter.services.integrity import FilePair, IntegrityError, local_crc32, verify_files


def test_local_crc32_matches_zlib(tmp_path: Path) -> None:
    """Calcula el mismo CRC32 que zlib leyendo por bloques e informa los bytes."""
    data = bytes(range(256)) * 50_000
    path = tmp_path / "a.bin"
    path.write_bytes(data)
    seen: list[int] = []
    assert local_crc32(path, seen.append, lambda: False) == zlib.crc32(data)
    assert sum(seen) == len(data)


def test_local_crc32_can_be_cancelled(tmp_path: Path) -> None:
    """Se detiene si se pide cancelar."""
    path = tmp_path / "a.bin"
    path.write_bytes(b"x" * 10)
    with pytest.raises(DownloadCancelledError):
        local_crc32(path, lambda _n: None, lambda: True)


def test_verify_files_reports_mismatches(tmp_path: Path) -> None:
    """Devuelve solo los archivos cuyo CRC32 difiere del de la PS5."""
    root = tmp_path / "ps5"
    (root / "data").mkdir(parents=True)
    (root / "data" / "a.bin").write_bytes(b"A" * 1000)
    (root / "data" / "b.bin").write_bytes(b"B" * 1000)
    (tmp_path / "a.bin").write_bytes(b"A" * 1000)
    (tmp_path / "b.bin").write_bytes(b"X" * 1000)
    console = FakeConsole(root, 0, usable=0)
    pairs = [FilePair(tmp_path / "a.bin", "/data/a.bin", 1000),
             FilePair(tmp_path / "b.bin", "/data/b.bin", 1000)]
    progress: list[tuple[int, int]] = []
    bad = verify_files(console, pairs, lambda d, t: progress.append((d, t)),  # type: ignore[arg-type]
                       lambda: False)
    assert bad == [pairs[1]]
    assert progress[-1] == (4000, 4000)


def test_integrity_error_lists_files() -> None:
    """El mensaje nombra los archivos que no coinciden y qué se comprobaba."""
    message = str(IntegrityError(["a", "b", "c", "d"], "la subida"))
    assert "la subida" in message and "a, b, c y 1 más" in message
