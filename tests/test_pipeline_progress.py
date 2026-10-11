from __future__ import annotations

from pathlib import Path

import pytest

from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions, ProgressUpdate
from ffpfsc_converter.domain.pipeline import PipelineStage
from ffpfsc_converter.domain.pipeline_events import PipelineProgress
from ffpfsc_converter.services.conversion import ConversionRunner
from ffpfsc_converter.services.pipeline import compress
from ffpfsc_converter.services.pipeline.reporter import PipelineReporter
from test_conversion import FakeProcess


def test_reporter_throttles_progress_but_keeps_the_end() -> None:
    """Miles de avances seguidos (CRC32, subida) se publican pocas veces, el 100 % siempre."""
    events: list[object] = []
    now = [0.0]
    reporter = PipelineReporter(events.append, clock=lambda: now[0])
    reporter.stage(PipelineStage.VERIFY_DOWNLOAD, "")
    for done in range(1, 10_001):
        now[0] = done * 0.0001  # 10 000 avances en 1 s
        reporter.report(done, 10_000, 0.0)
    progress = [e for e in events if isinstance(e, PipelineProgress)]
    assert 2 <= len(progress) <= 6
    assert progress[-1].percent == 100


def test_retry_notice_is_never_throttled() -> None:
    """El aviso de reintento se publica siempre, aunque acabe de publicarse un avance."""
    events: list[object] = []
    reporter = PipelineReporter(events.append, clock=lambda: 0.0)
    reporter.report(1, 10, 0.0)
    reporter.retry(1, 3, OSError("corte"))
    assert "Reintentando" in events[-1].detail  # type: ignore[attr-defined]


def test_compress_stage_receives_throttled_mkpfs_progress(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """La compresión de «comprimir y reemplazar» tampoco recibe una ráfaga de avances."""
    flood = [f"[1/2] {i % 100}% compress" for i in range(5000)] + ["[1/2] 100% compress"]
    monkeypatch.setattr(compress, "ConversionRunner", lambda sink: ConversionRunner(
        sink, process_factory=lambda cmd: FakeProcess(cmd, flood, 0)))
    image = tmp_path / "juego.exfat"
    image.write_bytes(b"x" * 100)
    job = ConversionJob(image, image, tmp_path / "juego.ffpfsc", size=100)
    seen: list[ProgressUpdate] = []
    result = compress.compress_job(job, ConversionOptions(3, 2, False),
                                   lambda progress, _eta: seen.append(progress), lambda: False)
    assert result.succeeded
    assert 1 <= len(seen) < 20 and seen[-1].percent == 100
