from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FakeConsole
from ffpfsc_converter.domain.pipeline import SpaceStrategy
from ffpfsc_converter.domain.pipeline_events import (
    RemoteDeleted,
    UploadFinished,
    UploadProgress,
)
from ffpfsc_converter.domain.remote import RemoteEntry
from ffpfsc_converter.domain.remote_events import FtpReady
from ffpfsc_converter.services.pipeline.plan import (
    build_replace_plan,
    choose_strategy,
    is_convertible,
)
from ffpfsc_converter.services.remote_changes import RemoteChanges

pytestmark = pytest.mark.filterwarnings("ignore:write permissions:RuntimeWarning")


def test_delete_uses_helper_and_reports(writable_ftp: int, ftp_root: Path) -> None:
    """Eliminar pide el borrado al helper y publica las rutas borradas."""
    console = FakeConsole(ftp_root, writable_ftp, usable=0)
    events: list[object] = []
    changes = RemoteChanges(events.append, console)  # type: ignore[arg-type]
    changes.delete("ps5", ["/data/homebrew/Juego"]).join(5)
    assert events[-1] == RemoteDeleted(("/data/homebrew/Juego",))
    assert not (ftp_root / "data" / "homebrew" / "Juego").exists()
    assert not changes.busy


def test_upload_is_verified_and_restores_readonly(writable_ftp: int, ftp_root: Path,
                                                   tmp_path: Path) -> None:
    """Subir usa escritura temporal, publica el archivo y vuelve a solo lectura."""
    local = tmp_path / "nuevo.ffpfsc"
    local.write_bytes(b"N" * 70_000)
    console = FakeConsole(ftp_root, writable_ftp, usable=10**9)
    events: list[object] = []
    changes = RemoteChanges(events.append, console)  # type: ignore[arg-type]
    ids = changes.upload("ps5", writable_ftp, [local], "/data/homebrew")
    while changes.busy:
        pass
    remote = ftp_root / "data" / "homebrew" / "nuevo.ffpfsc"
    assert remote.read_bytes() == local.read_bytes()
    assert UploadFinished(ids[0], True, "/data/homebrew/nuevo.ffpfsc") in events
    assert any(isinstance(e, UploadProgress) for e in events)
    assert isinstance(events[-1], FtpReady) and console.modes == [True, False]


def test_upload_skips_file_already_on_console(writable_ftp: int, ftp_root: Path,
                                             tmp_path: Path) -> None:
    """No vuelve a subir un archivo que ya está en la PS5 con el mismo tamaño."""
    local = tmp_path / "listo.ffpfsc"
    local.write_bytes(b"L" * 5_000)
    (ftp_root / "data" / "homebrew" / "listo.ffpfsc").write_bytes(b"L" * 5_000)
    console = FakeConsole(ftp_root, writable_ftp, usable=10**9)
    events: list[object] = []
    changes = RemoteChanges(events.append, console)  # type: ignore[arg-type]
    ids = changes.upload("ps5", writable_ftp, [local], "/data/homebrew")
    while changes.busy:
        pass
    message = "/data/homebrew/listo.ffpfsc (ya estaba en la PS5)"
    assert UploadFinished(ids[0], True, message) in events
    assert not any(isinstance(e, UploadProgress) for e in events)


def test_upload_resumes_existing_part(writable_ftp: int, ftp_root: Path, tmp_path: Path) -> None:
    """Una subida cortada continúa desde la parte que ya está en la PS5."""
    local = tmp_path / "grande.ffpfsc"
    local.write_bytes(b"A" * 30_000 + b"B" * 30_000)
    (ftp_root / "data" / "homebrew" / "grande.ffpfsc.part").write_bytes(b"A" * 30_000)
    console = FakeConsole(ftp_root, writable_ftp, usable=10**9)
    changes = RemoteChanges(lambda _e: None, console)  # type: ignore[arg-type]
    changes.upload("ps5", writable_ftp, [local], "/data/homebrew")
    while changes.busy:
        pass
    assert (ftp_root / "data" / "homebrew" / "grande.ffpfsc").read_bytes() == local.read_bytes()


def test_convertible_entries() -> None:
    """Solo carpetas e imágenes .exfat/.ffpkg se pueden comprimir."""
    assert is_convertible(RemoteEntry("Juego", "/d/Juego", True))
    assert is_convertible(RemoteEntry("x.EXFAT", "/d/x.EXFAT", False))
    assert not is_convertible(RemoteEntry("x.ffpfsc", "/d/x.ffpfsc", False))


def test_replace_plan_names() -> None:
    """El .ffpfsc va en la misma carpeta, con el nombre sin extensión de imagen."""
    plan = build_replace_plan(RemoteEntry("Juego.exfat", "/mnt/usb0/Juego.exfat", False),
                              ["Juego.exfat", "Juego.ffpfsc"])
    assert plan.remote_final == "/mnt/usb0/Juego.ffpfsc"
    assert plan.remote_part == "/mnt/usb0/Juego.ffpfsc.part"
    assert plan.final_exists


@pytest.mark.parametrize(("usable", "uploaded", "expected"), [
    (100, 0, SpaceStrategy.UPLOAD_FIRST),
    (60, 0, SpaceStrategy.DELETE_FIRST),
    (10, 0, SpaceStrategy.INSUFFICIENT),
    (10, 95, SpaceStrategy.UPLOAD_FIRST),
])
def test_choose_strategy(usable: int, uploaded: int, expected: SpaceStrategy) -> None:
    """Elige subir primero, borrar primero o rechazar según el espacio."""
    assert choose_strategy(usable, 100, uploaded, original_size=50) is expected


def test_upload_restarts_when_remote_part_is_from_another_file(
        writable_ftp: int, ftp_root: Path, tmp_path: Path) -> None:
    """Una parte remota de otro archivo (p. ej. otra compresión) no se reanuda: se reemplaza."""
    local = tmp_path / "juego.ffpfsc"
    local.write_bytes(b"N" * 50_000)
    (ftp_root / "data" / "homebrew" / "juego.ffpfsc.part").write_bytes(b"V" * 20_000)
    console = FakeConsole(ftp_root, writable_ftp, usable=10**9)
    changes = RemoteChanges(lambda _e: None, console)  # type: ignore[arg-type]
    changes.upload("ps5", writable_ftp, [local], "/data/homebrew")
    while changes.busy:
        pass
    assert (ftp_root / "data" / "homebrew" / "juego.ffpfsc").read_bytes() == local.read_bytes()
