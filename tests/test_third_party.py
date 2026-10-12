from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from pathlib import Path

import pytest

from ffpfsc_converter.config import THIRD_PARTY_ASSETS
from ffpfsc_converter.domain.third_party import ThirdPartyAsset
from ffpfsc_converter.infrastructure.third_party import (
    ChecksumMismatchError,
    fetch,
    installed,
    is_current,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from fetch_third_party import fetch_all

ELF = b"\x7fELF payload"
PREFIX = "pack/python-tools/"


def _zip(members: dict[str, bytes]) -> bytes:
    """Arma un .zip en memoria con los miembros indicados."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def _asset(data: bytes, target: str = "x/file.elf", prefix: str = "") -> ThirdPartyAsset:
    """Crea un archivo de terceros cuya huella es la de ``data``."""
    return ThirdPartyAsset("prueba", "https://example/file", hashlib.sha256(data).hexdigest(),
                           target, prefix)


def _opener(data: bytes, calls: list[str] | None = None):
    """Devuelve un opener falso que entrega siempre ``data``."""
    def open_url(url: str) -> io.BytesIO:
        """Registra la URL pedida y entrega los bytes fijos."""
        if calls is not None:
            calls.append(url)
        return io.BytesIO(data)
    return open_url


def test_file_is_downloaded_verified_and_kept(tmp_path: Path) -> None:
    """Descarga el archivo, lo deja en su destino y no lo vuelve a bajar si está al día."""
    asset, calls = _asset(ELF), []
    assert fetch(asset, tmp_path, _opener(ELF, calls)) is True
    assert (tmp_path / "x/file.elf").read_bytes() == ELF and is_current(asset, tmp_path)
    assert fetch(asset, tmp_path, _opener(ELF, calls)) is False
    assert calls == ["https://example/file"]
    assert installed("x/file.elf", tmp_path) == tmp_path / "x/file.elf"
    assert installed("x/otro.elf", tmp_path) is None


def test_wrong_checksum_places_nothing(tmp_path: Path) -> None:
    """Si la huella no coincide no se coloca el archivo ni quedan temporales."""
    with pytest.raises(ChecksumMismatchError):
        fetch(_asset(ELF), tmp_path, _opener(b"otra cosa"))
    assert not (tmp_path / "x/file.elf").exists()
    assert list(tmp_path.iterdir()) == []


def test_archive_extracts_only_the_prefix(tmp_path: Path) -> None:
    """Del .zip solo se extrae lo que está bajo el prefijo, sin él, y se recuerda la huella."""
    data = _zip({f"{PREFIX}ampr_pack.py": b"print()", f"{PREFIX}sub/a.txt": b"a",
                 "pack/ampr_pack_gui.exe": b"MZ"})
    asset = _asset(data, "tools", PREFIX)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "viejo.py").write_text("x")
    assert fetch(asset, tmp_path, _opener(data)) is True
    files = sorted(p.relative_to(tmp_path / "tools").as_posix()
                   for p in (tmp_path / "tools").rglob("*") if p.is_file())
    assert files == [".sha256", "ampr_pack.py", "sub/a.txt"]
    assert is_current(asset, tmp_path)


def test_archive_member_cannot_escape(tmp_path: Path) -> None:
    """Un miembro con ``..`` que saldría de la carpeta se rechaza."""
    data = _zip({f"{PREFIX}../../fuera.py": b"x"})
    with pytest.raises(OSError):
        fetch(_asset(data, "tools", PREFIX), tmp_path, _opener(data))
    assert not (tmp_path / "fuera.py").exists()


def test_fetch_all_reports_failures_and_continues(tmp_path: Path,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    """Un fallo no detiene las demás descargas y queda en la lista de avisos."""
    good, bad = _asset(ELF, "a.elf"), _asset(b"distinto", "b.elf")
    failures = fetch_all([bad, good], tmp_path, _opener(ELF))
    assert len(failures) == 1 and (tmp_path / "a.elf").is_file()
    assert "✓ prueba" in capsys.readouterr().out


def test_manifest_is_pinned() -> None:
    """Cada archivo fijado usa HTTPS de GitHub, una huella completa y un destino relativo."""
    for asset in THIRD_PARTY_ASSETS:
        assert asset.url.startswith("https://github.com/") and len(asset.sha256) == 64
        assert not Path(asset.target).is_absolute() and ".." not in asset.target
