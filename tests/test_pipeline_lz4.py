from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FakeConsole
from ffpfsc_converter import config
from ffpfsc_converter.domain.models import ConversionResult, OutputFormat
from ffpfsc_converter.domain.pipeline import PipelineChoice, PipelineStage
from ffpfsc_converter.domain.pipeline_events import (
    PipelineFinished,
    PipelineOptionsRequired,
    PipelineStageChanged,
)
from ffpfsc_converter.domain.remote import ConsoleTarget, RemoteEntry
from ffpfsc_converter.infrastructure.ftp import FtpClient
from ffpfsc_converter.services.lz4_local_files import lz4_options, planned_output
from ffpfsc_converter.services.pipeline.plan import build_replace_plan, can_use_lz4
from ffpfsc_converter.services.pipeline.runner import Ps5ConversionPipeline
from ffpfsc_converter.services.remote_folder_files import UploadHooks
from ffpfsc_converter.services.remote_folder_upload import rename_remote

pytestmark = pytest.mark.filterwarnings("ignore:write permissions:RuntimeWarning")

GAME = RemoteEntry("Juego", "/data/homebrew/Juego", True)
LZ4_FILES = {
    "eboot.bin": b"N" * 30_000,
    "sce_sys/param.json": b'{"titleId": "PPSA00000"}',
    "ampr_assets-000.pak": b"P" * 70_000,
    "ampr_emu.index": b"I" * 2_000,
    "fakelib/libSceAmpr.sprx": b"S" * 1_000,
}
CHOICE = PipelineChoice(lz4_options(3, 2, True), delete_local=True)


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reintentos sin esperas para que los tests sean rápidos."""
    monkeypatch.setattr(config, "RETRY_DELAYS_SECONDS", (0.0, 0.0, 0.0))


def fake_lz4(job: object, options: object, on_progress: object,
             should_cancel: object) -> ConversionResult:
    """Arma una carpeta LZ4 de prueba en lugar de ejecutar ampr_emu."""
    output = planned_output(job, options)  # type: ignore[arg-type]
    for relative, data in LZ4_FILES.items():
        (output / relative).parent.mkdir(parents=True, exist_ok=True)
        (output / relative).write_bytes(data)
    return ConversionResult(True, False, 0.1)


def _pipeline(console: FakeConsole, events: list[object],
              choice: PipelineChoice | None = CHOICE) -> Ps5ConversionPipeline:
    """Crea un pipeline que contesta la ventana de compresión con ``choice``."""
    def emit(event: object) -> None:
        """Registra el evento y contesta la ventana de compresión."""
        events.append(event)
        if isinstance(event, PipelineOptionsRequired):
            pipeline.answer(choice)

    pipeline = Ps5ConversionPipeline(emit, console, compressor=fake_lz4)  # type: ignore[arg-type]
    return pipeline


def _tree(root: Path) -> dict[str, bytes]:
    """Lee una carpeta como ruta relativa → bytes."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_lz4_plan_keeps_the_original_name() -> None:
    """La carpeta LZ4 ocupa el lugar del original con su mismo nombre."""
    plan = build_replace_plan(GAME, ["Juego", "Juego.ffpfsc"], OutputFormat.LZ4)
    assert plan.remote_final == "/data/homebrew/Juego"
    assert plan.remote_part == "/data/homebrew/Juego.part"
    assert not plan.final_exists


def test_replaces_folder_with_lz4_folder(writable_ftp: int, ftp_root: Path,
                                         tmp_path: Path) -> None:
    """Sube la carpeta LZ4 verificada archivo por archivo y la deja con el nombre original."""
    console, events = FakeConsole(ftp_root, writable_ftp, usable=10**9), []
    pipeline = _pipeline(console, events)
    pipeline.start(GAME, ConsoleTarget("127.0.0.1", writable_ftp), ["Juego"],
                   tmp_path / "work").join(20)
    result = events[-1].result
    assert isinstance(events[-1], PipelineFinished) and result.succeeded, result.message
    homebrew = ftp_root / "data" / "homebrew"
    assert _tree(homebrew / "Juego") == LZ4_FILES
    assert not (homebrew / "Juego.part").exists()
    assert "/data/homebrew/Juego.part/ampr_emu.index" in console.crc_paths
    stages = [e.stage for e in events if isinstance(e, PipelineStageChanged)]
    assert stages.index(PipelineStage.VERIFY_UPLOAD) < stages.index(PipelineStage.DELETE_ORIGINAL)
    assert console.modes == [True, False]
    assert not (tmp_path / "work").exists()
    options = next(e for e in events if isinstance(e, PipelineOptionsRequired))
    assert options.lz4_plan is not None and options.lz4_plan.remote_final == GAME.path


def test_lz4_is_offered_only_for_folders() -> None:
    """Una imagen no se puede revisar por dentro: solo las carpetas admiten LZ4."""
    assert can_use_lz4(GAME)
    assert not can_use_lz4(RemoteEntry("Juego.exfat", "/data/homebrew/Juego.exfat", False))


def test_corrupted_lz4_file_is_reuploaded_on_retry(writable_ftp: int, ftp_root: Path,
                                                   tmp_path: Path) -> None:
    """Un archivo dañado frena el reemplazo sin tocar el original; «Reintentar» lo resube."""
    console, events = FakeConsole(ftp_root, writable_ftp, usable=10**9), []
    bad = "/data/homebrew/Juego.part/ampr_emu.index"
    console.crc_override[bad] = 1
    pipeline = _pipeline(console, events)
    target = ConsoleTarget("127.0.0.1", writable_ftp)
    pipeline.start(GAME, target, ["Juego"], tmp_path / "work").join(20)
    homebrew = ftp_root / "data" / "homebrew"
    assert not events[-1].result.succeeded and "la subida" in events[-1].result.message
    assert (homebrew / "Juego" / "eboot.bin").read_bytes() == b"E" * 300_000
    assert console.deleted == [bad] and (homebrew / "Juego.part" / "eboot.bin").exists()

    console.crc_override.clear()
    pipeline.retry(target).join(20)
    assert events[-1].result.succeeded, events[-1].result.message
    assert _tree(homebrew / "Juego") == LZ4_FILES


def test_rename_already_done_is_not_repeated(writable_ftp: int, ftp_root: Path) -> None:
    """Si un renombre se hizo pero su respuesta se perdió, el reintento no falla."""
    homebrew = ftp_root / "data" / "homebrew"
    (homebrew / "Juego").rename(homebrew / "Nuevo")
    hooks = UploadHooks(lambda *_args: None, lambda: False, lambda *_args: None)
    rename_remote(FtpClient, ConsoleTarget("127.0.0.1", writable_ftp),
                  "/data/homebrew/Juego", "/data/homebrew/Nuevo", hooks)
    assert (homebrew / "Nuevo" / "eboot.bin").exists()
