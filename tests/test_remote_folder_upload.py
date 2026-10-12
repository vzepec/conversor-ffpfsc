from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FakeConsole
from ffpfsc_converter.domain.pipeline_events import UploadFinished, UploadProgress
from ffpfsc_converter.services.remote_changes import RemoteChanges
from ffpfsc_converter.services.remote_folder_files import folder_files, remote_dirs

pytestmark = pytest.mark.filterwarnings("ignore:write permissions:RuntimeWarning")


def _game(tmp_path: Path) -> Path:
    """Crea una carpeta local con subcarpetas, como un juego convertido a LZ4."""
    game = tmp_path / "Juego-LZ4"
    (game / "sce_sys").mkdir(parents=True)
    (game / "fakelib").mkdir()
    (game / "eboot.bin").write_bytes(b"E" * 40_000)
    (game / "sce_sys/param.json").write_text('{"titleId": "PPSA01234"}')
    (game / "fakelib/libSceAmpr.sprx").write_bytes(b"S" * 3_000)
    (game / "ampr_assets-000.pak").write_bytes(b"P" * 90_000)
    return game


def _upload(ftp_root: Path, port: int, local: Path) -> tuple[list[object], RemoteChanges]:
    """Sube una carpeta a /data/homebrew y espera a que termine."""
    (ftp_root / "data" / "homebrew").mkdir(parents=True, exist_ok=True)
    console = FakeConsole(ftp_root, port, usable=10**9)
    events: list[object] = []
    changes = RemoteChanges(events.append, console)  # type: ignore[arg-type]
    changes.upload("ps5", port, [local], "/data/homebrew")
    while changes.busy:
        pass
    return events, changes


def _tree(root: Path) -> dict[str, bytes]:
    """Lee el contenido de una carpeta como ruta relativa → bytes."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_remote_dirs_go_from_outer_to_inner(tmp_path: Path) -> None:
    """Las subcarpetas se crean de afuera hacia adentro, sin la raíz."""
    files = folder_files(_game(tmp_path))
    assert files[0].relative == "ampr_assets-000.pak"
    assert remote_dirs(files) == ["fakelib", "sce_sys"]


def test_folder_is_uploaded_whole_and_published_at_the_end(writable_ftp: int, ftp_root: Path,
                                                           tmp_path: Path) -> None:
    """La carpeta llega idéntica, con una sola fila, y no queda la temporal ``.part``."""
    local = _game(tmp_path)
    events, _ = _upload(ftp_root, writable_ftp, local)
    remote = ftp_root / "data/homebrew/Juego-LZ4"
    assert _tree(remote) == _tree(local)
    assert not (ftp_root / "data/homebrew/Juego-LZ4.part").exists()
    finished = [e for e in events if isinstance(e, UploadFinished)]
    assert len(finished) == 1 and finished[0].succeeded
    assert finished[0].message == "/data/homebrew/Juego-LZ4"
    progress = [e for e in events if isinstance(e, UploadProgress)]
    assert progress and progress[-1].total == sum(len(v) for v in _tree(local).values())


def test_existing_folder_is_never_overwritten(writable_ftp: int, ftp_root: Path,
                                              tmp_path: Path) -> None:
    """Si ya hay una carpeta con ese nombre, falla sin tocarla."""
    existing = ftp_root / "data/homebrew/Juego-LZ4"
    existing.mkdir(parents=True)
    (existing / "mio.txt").write_text("no tocar")
    events, _ = _upload(ftp_root, writable_ftp, _game(tmp_path))
    finished = next(e for e in events if isinstance(e, UploadFinished))
    assert not finished.succeeded and "Ya existe" in finished.message
    assert _tree(existing) == {"mio.txt": b"no tocar"}


def test_retry_skips_files_already_complete(writable_ftp: int, ftp_root: Path,
                                            tmp_path: Path) -> None:
    """Al reintentar, lo que ya estaba completo en la carpeta temporal no se vuelve a subir."""
    local = _game(tmp_path)
    staging = ftp_root / "data/homebrew/Juego-LZ4.part"
    staging.mkdir(parents=True)
    done = staging / "ampr_assets-000.pak"
    done.write_bytes((local / "ampr_assets-000.pak").read_bytes())
    stamp = done.stat().st_mtime_ns
    events, _ = _upload(ftp_root, writable_ftp, local)
    assert next(e for e in events if isinstance(e, UploadFinished)).succeeded
    published = ftp_root / "data/homebrew/Juego-LZ4/ampr_assets-000.pak"
    assert published.stat().st_mtime_ns == stamp


def test_cancelled_folder_leaves_no_final_folder(writable_ftp: int, ftp_root: Path,
                                                 tmp_path: Path) -> None:
    """Si se cancela, no aparece la carpeta definitiva (lo subido queda para reintentar)."""
    (ftp_root / "data" / "homebrew").mkdir(parents=True, exist_ok=True)
    console = FakeConsole(ftp_root, writable_ftp, usable=10**9)
    events: list[object] = []
    changes = RemoteChanges(events.append, console)  # type: ignore[arg-type]
    changes.upload("ps5", writable_ftp, [_game(tmp_path)], "/data/homebrew")
    changes.cancel()
    while changes.busy:
        pass
    assert not (ftp_root / "data/homebrew/Juego-LZ4").exists()
    finished = next(e for e in events if isinstance(e, UploadFinished))
    assert not finished.succeeded
