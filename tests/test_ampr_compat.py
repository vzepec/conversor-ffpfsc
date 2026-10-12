from __future__ import annotations

from pathlib import Path

import pytest

from ffpfsc_converter.domain.lz4 import Lz4Compat
from ffpfsc_converter.services.ampr_compat import detect_compat


def _game(tmp_path: Path, eboot: bytes) -> Path:
    """Crea una carpeta de juego con el ``eboot.bin`` indicado."""
    root = tmp_path / "game"
    (root / "sce_module").mkdir(parents=True)
    (root / "eboot.bin").write_bytes(eboot)
    return root


def test_eboot_importing_libsceampr_is_compatible(tmp_path: Path) -> None:
    """Si ``eboot.bin`` nombra a ``libSceAmpr``, el juego admite LZ4."""
    assert detect_compat(_game(tmp_path, b"\0libkernel\0libSceAmpr\0")) is Lz4Compat.YES


def test_module_importing_libsceampr_is_compatible(tmp_path: Path) -> None:
    """También cuenta un módulo de ``sce_module`` que la importe."""
    root = _game(tmp_path, b"\0libkernel\0")
    (root / "sce_module" / "game.prx").write_bytes(b"x" * 10 + b"libSceAmpr")
    assert detect_compat(root) is Lz4Compat.YES


def test_readable_without_libsceampr_is_not_compatible(tmp_path: Path) -> None:
    """Ejecutables legibles (``libkernel``) sin ``libSceAmpr``: no admite LZ4."""
    assert detect_compat(_game(tmp_path, b"\0libkernel\0libc\0")) is Lz4Compat.NO


def test_encrypted_or_missing_is_unknown(tmp_path: Path) -> None:
    """Si no se puede leer nada útil, o es una imagen, no se sabe."""
    assert detect_compat(_game(tmp_path, b"\x00" * 64)) is Lz4Compat.UNKNOWN
    image = tmp_path / "juego.exfat"
    image.write_bytes(b"x")
    assert detect_compat(image) is Lz4Compat.UNKNOWN


def test_name_split_between_reads_is_found(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """Un nombre partido entre dos lecturas se encuentra igual."""
    import ffpfsc_converter.services.ampr_compat as compat
    monkeypatch.setattr(compat, "_CHUNK", 8)
    assert detect_compat(_game(tmp_path, b"1234libSceAmpr")) is Lz4Compat.YES
