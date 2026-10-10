from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FakeConsole
from ffpfsc_converter.domain.models import ConversionOptions, ConversionResult
from ffpfsc_converter.domain.pipeline import PipelineChoice, PipelineStage
from ffpfsc_converter.domain.pipeline_events import (
    PipelineConfirmRequired,
    PipelineFinished,
    PipelineOptionsRequired,
    PipelineStageChanged,
)
from ffpfsc_converter.domain.remote import ConsoleTarget, RemoteEntry
from ffpfsc_converter.domain.remote_events import FtpReady
from ffpfsc_converter.services.pipeline.runner import Ps5ConversionPipeline

pytestmark = pytest.mark.filterwarnings("ignore:write permissions:RuntimeWarning")

GAME = RemoteEntry("Juego", "/data/homebrew/Juego", True)
COMPRESSED = b"C" * 40_000


def fake_compress(job: object, options: object, on_progress: object,
                  should_cancel: object) -> ConversionResult:
    """Escribe un .ffpfsc de prueba en lugar de ejecutar MkPFS."""
    job.output.write_bytes(COMPRESSED)  # type: ignore[attr-defined]
    return ConversionResult(True, False, 0.1, output_size=len(COMPRESSED))


def _run(console: FakeConsole, port: int, tmp_path: Path, answers: dict[type, object],
         siblings: tuple[str, ...] = ("Juego", "imagen.ffpfsc")) -> list[object]:
    """Ejecuta el pipeline respondiendo automáticamente y devuelve los eventos."""
    events: list[object] = []

    def emit(event: object) -> None:
        """Registra el evento y contesta las preguntas como lo haría la interfaz."""
        events.append(event)
        if type(event) in answers:
            pipeline.answer(answers[type(event)])

    pipeline = Ps5ConversionPipeline(emit, console, compressor=fake_compress)  # type: ignore[arg-type]
    pipeline.start(GAME, ConsoleTarget("127.0.0.1", port), siblings, tmp_path / "work").join(20)
    assert not pipeline.busy
    return events


CHOICE = PipelineChoice(ConversionOptions(3, 2, False), delete_local=True)


def test_replaces_folder_with_compressed_image(writable_ftp: int, ftp_root: Path,
                                               tmp_path: Path) -> None:
    """Descarga, comprime, sube verificado, borra el original y limpia lo local."""
    console = FakeConsole(ftp_root, writable_ftp, usable=10**9)
    events = _run(console, writable_ftp, tmp_path, {PipelineOptionsRequired: CHOICE})
    result = events[-1].result
    assert isinstance(events[-1], PipelineFinished) and result.succeeded, result.message
    homebrew = ftp_root / "data" / "homebrew"
    assert not (homebrew / "Juego").exists()
    assert (homebrew / "Juego.ffpfsc").read_bytes() == COMPRESSED
    assert not (homebrew / "Juego.ffpfsc.part").exists()
    assert console.modes == [True, False]  # escritura solo durante el reemplazo
    assert any(isinstance(e, FtpReady) for e in events)
    stages = [e.stage for e in events if isinstance(e, PipelineStageChanged)]
    assert stages.index(PipelineStage.UPLOAD) < stages.index(PipelineStage.DELETE_ORIGINAL)
    assert not (tmp_path / "work" / "Juego").exists()


def test_low_space_declined_keeps_everything(writable_ftp: int, ftp_root: Path,
                                             tmp_path: Path) -> None:
    """Si solo cabe borrando antes y el usuario no acepta, no se borra nada."""
    console = FakeConsole(ftp_root, writable_ftp, usable=1000)
    answers = {PipelineOptionsRequired: CHOICE, PipelineConfirmRequired: False}
    result = _run(console, writable_ftp, tmp_path, answers)[-1].result
    assert not result.succeeded and "no se borró nada" in result.message
    assert (ftp_root / "data" / "homebrew" / "Juego" / "eboot.bin").exists()
    assert console.deleted == [] and console.modes == []
    assert (tmp_path / "work" / "Juego" / "eboot.bin").exists()  # copia local intacta


def test_low_space_accepted_deletes_first(writable_ftp: int, ftp_root: Path,
                                          tmp_path: Path) -> None:
    """Si el usuario acepta, borra primero y luego sube."""
    console = FakeConsole(ftp_root, writable_ftp, usable=1000)
    answers = {PipelineOptionsRequired: CHOICE, PipelineConfirmRequired: True}
    events = _run(console, writable_ftp, tmp_path, answers)
    assert events[-1].result.succeeded
    stages = [e.stage for e in events if isinstance(e, PipelineStageChanged)]
    assert stages.index(PipelineStage.DELETE_ORIGINAL) < stages.index(PipelineStage.UPLOAD)


def test_insufficient_space_fails_without_changes(writable_ftp: int, ftp_root: Path,
                                                  tmp_path: Path) -> None:
    """Si no cabe ni borrando el original, falla sin tocar la PS5."""
    console = FakeConsole(ftp_root, writable_ftp, usable=0)
    big = ftp_root / "data" / "homebrew" / "Juego" / "eboot.bin"
    big.write_bytes(b"E" * 10)  # original más chico que el comprimido
    result = _run(console, writable_ftp, tmp_path, {PipelineOptionsRequired: CHOICE})[-1].result
    assert not result.succeeded and "no tiene espacio" in result.message
    assert console.deleted == [] and big.exists()


def test_cancel_in_options_dialog(writable_ftp: int, ftp_root: Path, tmp_path: Path) -> None:
    """Cancelar la ventana de compresión no toca la PS5 y conserva la descarga."""
    console = FakeConsole(ftp_root, writable_ftp, usable=10**9)
    result = _run(console, writable_ftp, tmp_path, {PipelineOptionsRequired: None})[-1].result
    assert result.cancelled and console.modes == [] and console.deleted == []
    assert (tmp_path / "work" / "Juego" / "eboot.bin").exists()
