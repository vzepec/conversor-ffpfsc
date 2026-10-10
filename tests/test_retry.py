from __future__ import annotations

import ftplib
from pathlib import Path

import pytest

from conftest import FakeConsole
from ffpfsc_converter import config
from ffpfsc_converter.domain.models import ConversionOptions, ConversionResult
from ffpfsc_converter.domain.pipeline import PipelineChoice
from ffpfsc_converter.domain.pipeline_events import (
    PipelineFinished,
    PipelineOptionsRequired,
    UploadFinished,
)
from ffpfsc_converter.domain.remote import (
    ConsoleTarget,
    DownloadJob,
    DownloadState,
    RemoteEntry,
)
from ffpfsc_converter.domain.remote_events import TransferRetrying
from ffpfsc_converter.errors import DownloadCancelledError
from ffpfsc_converter.infrastructure.ftp import FtpClient
from ffpfsc_converter.services.downloads import DownloadRunner
from ffpfsc_converter.services.pipeline.runner import Ps5ConversionPipeline
from ffpfsc_converter.services.remote_changes import RemoteChanges
from ffpfsc_converter.services.retry import is_transient, with_retries

pytestmark = pytest.mark.filterwarnings("ignore:write permissions:RuntimeWarning")


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reintentos sin esperas para que los tests sean rápidos."""
    monkeypatch.setattr(config, "RETRY_DELAYS_SECONDS", (0.0, 0.0, 0.0))


class Flaky(FtpClient):
    """FtpClient que corta la conexión en las primeras ``failures`` transferencias."""

    failures = 0

    def download(self, *args: object, **kwargs: object) -> None:
        """Falla como un corte de red mientras queden fallos programados."""
        if Flaky.failures > 0:
            Flaky.failures -= 1
            raise ConnectionResetError("corte simulado")
        super().download(*args, **kwargs)  # type: ignore[arg-type]

    def upload(self, *args: object, **kwargs: object) -> None:
        """Falla como un corte de red mientras queden fallos programados."""
        if Flaky.failures > 0:
            Flaky.failures -= 1
            raise ConnectionResetError("corte simulado")
        super().upload(*args, **kwargs)  # type: ignore[arg-type]


def test_is_transient_classification() -> None:
    """Solo los cortes y verificaciones fallidas se reintentan."""
    assert is_transient(ConnectionResetError())
    assert is_transient(TimeoutError())
    assert is_transient(ftplib.error_temp("421 timeout"))
    assert not is_transient(ftplib.error_perm("550 no existe"))
    assert not is_transient(DownloadCancelledError())


def test_with_retries_succeeds_after_failures() -> None:
    """Reintenta hasta lograrlo y avisa cada reintento."""
    calls, notices = [0], []

    def action() -> str:
        """Falla dos veces y luego funciona."""
        calls[0] += 1
        if calls[0] < 3:
            raise ConnectionResetError()
        return "ok"

    assert with_retries(action, lambda a, m, e: notices.append((a, m)), lambda: False) == "ok"
    assert notices == [(1, 3), (2, 3)]


def test_with_retries_gives_up_and_skips_permanent_errors() -> None:
    """Tras 3 reintentos se rinde; un error definitivo no se reintenta."""
    calls = [0]

    def always_cut() -> None:
        """Siempre falla con un corte."""
        calls[0] += 1
        raise ConnectionResetError()

    with pytest.raises(ConnectionResetError):
        with_retries(always_cut, lambda *_a: None, lambda: False)
    assert calls[0] == 4
    with pytest.raises(ftplib.error_perm):
        with_retries(lambda: (_ for _ in ()).throw(ftplib.error_perm("550")),
                     lambda *_a: pytest.fail("no debía reintentar"), lambda: False)


def test_download_recovers_from_cut(ftp_server: int, tmp_path: Path) -> None:
    """Una descarga cortada dos veces se completa sola."""
    Flaky.failures = 2
    events: list[object] = []
    job = DownloadJob(RemoteEntry("imagen.ffpfsc", "/data/homebrew/imagen.ffpfsc", False,
                                  50_000), tmp_path)
    DownloadRunner(events.append, client_factory=Flaky).start(
        [job], ConsoleTarget("127.0.0.1", ftp_server)).join(10)
    assert job.state is DownloadState.SUCCEEDED
    assert sum(isinstance(e, TransferRetrying) for e in events) == 2


def test_upload_fails_after_retries_and_marks_rows(writable_ftp: int, ftp_root: Path,
                                                   tmp_path: Path) -> None:
    """Si sigue fallando, la subida y las siguientes quedan como fallidas."""
    Flaky.failures = 99
    files = [tmp_path / "a.bin", tmp_path / "b.bin"]
    for f in files:
        f.write_bytes(b"x" * 1000)
    events: list[object] = []
    changes = RemoteChanges(events.append, FakeConsole(ftp_root, writable_ftp, 10**9),
                            client_factory=Flaky)  # type: ignore[arg-type]
    ids = changes.upload("ps5", writable_ftp, files, "/data/homebrew")
    while changes.busy:
        pass
    finished = [e for e in events if isinstance(e, UploadFinished)]
    assert [(e.upload_id, e.succeeded) for e in finished] == [(ids[0], False), (ids[1], False)]
    assert sum(isinstance(e, TransferRetrying) for e in events) == 3
    Flaky.failures = 0


class BrokenUpload(FtpClient):
    """FtpClient cuyas subidas fallan mientras ``broken`` sea verdadero."""

    broken = True

    def upload(self, *args: object, **kwargs: object) -> None:
        """Falla como un corte de red mientras esté roto."""
        if BrokenUpload.broken:
            raise ConnectionResetError("corte simulado")
        super().upload(*args, **kwargs)  # type: ignore[arg-type]


def test_manual_pipeline_retry_skips_compression(writable_ftp: int, ftp_root: Path,
                                                 tmp_path: Path) -> None:
    """Si la subida falla tras los reintentos, «Reintentar» retoma sin volver a comprimir."""
    compressions = [0]

    def compress(job: object, *_args: object) -> ConversionResult:
        """Cuenta las compresiones y escribe un .ffpfsc de prueba."""
        compressions[0] += 1
        job.output.write_bytes(b"C" * 5000)  # type: ignore[attr-defined]
        return ConversionResult(True, False, 0.1)

    events: list[object] = []
    choice = PipelineChoice(ConversionOptions(3, 1, False), delete_local=False)

    def emit(event: object) -> None:
        """Registra y contesta la ventana de compresión."""
        events.append(event)
        if isinstance(event, PipelineOptionsRequired):
            pipeline.answer(choice)

    console = FakeConsole(ftp_root, writable_ftp, 10**9)
    pipeline = Ps5ConversionPipeline(emit, console, client_factory=BrokenUpload,  # type: ignore[arg-type]
                                     compressor=compress)
    target = ConsoleTarget("127.0.0.1", writable_ftp)
    homebrew = ftp_root / "data" / "homebrew"
    BrokenUpload.broken = True
    pipeline.start(RemoteEntry("Juego", "/data/homebrew/Juego", True), target,
                   ["Juego"], tmp_path / "w").join(20)
    first = events[-1]
    assert isinstance(first, PipelineFinished) and not first.result.succeeded
    assert "Reintentar" in first.result.message
    assert (homebrew / "Juego").is_dir() and console.deleted == []  # original intacto

    BrokenUpload.broken = False
    pipeline.retry(target).join(20)
    assert events[-1].result.succeeded, events[-1].result.message
    assert compressions[0] == 1  # no se volvió a comprimir
    assert (homebrew / "Juego.ffpfsc").read_bytes() == b"C" * 5000
    assert not (homebrew / "Juego").exists() and pipeline.last is None
