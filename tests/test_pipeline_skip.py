from __future__ import annotations

import threading
from pathlib import Path

import pytest

from ffpfsc_converter.config import LZ4_VERIFY_PHASE
from ffpfsc_converter.domain.events import JobFinished
from ffpfsc_converter.domain.models import (
    ConversionJob,
    ConversionOptions,
    ConversionResult,
    ProgressUpdate,
)
from ffpfsc_converter.domain.pipeline_events import PipelineProgress
from ffpfsc_converter.services.pipeline import compress
from ffpfsc_converter.services.pipeline.reporter import PipelineReporter
from ffpfsc_converter.services.pipeline.runner import Ps5ConversionPipeline


def test_reporter_marks_only_lz4_verification_as_skippable() -> None:
    """Solo la verificación LZ4 permite saltarla; la de MkPFS y las demás fases no."""
    events: list[PipelineProgress] = []
    reporter = PipelineReporter(events.append)  # type: ignore[arg-type]
    for phase in ("compress", "verify", LZ4_VERIFY_PHASE):
        reporter.on_compress(ProgressUpdate(10, phase), None)
    assert [e.can_skip for e in events] == [False, False, True]


def test_skip_request_is_taken_once() -> None:
    """El pedido de saltar se consume una sola vez."""
    pipeline = Ps5ConversionPipeline(lambda _e: None, object())  # type: ignore[arg-type]
    assert not pipeline._take_skip()
    pipeline.skip_verification()
    assert pipeline._take_skip() and not pipeline._take_skip()


class _FakeRunner:
    """Runner que espera hasta que le pidan saltar la verificación."""

    skipped = 0

    def __init__(self, sink: object) -> None:
        """Guarda el destino de eventos."""
        self._sink, self._done = sink, threading.Event()
        self.cancel_requested = False

    def start(self, jobs: list[ConversionJob], options: ConversionOptions) -> threading.Thread:
        """Simula una verificación larga que termina bien al saltarla."""
        def work() -> None:
            """Espera el pedido y publica el resultado."""
            self._done.wait(10)
            self._sink(JobFinished(jobs[0], ConversionResult(True, False, 0.1)))  # type: ignore[operator]

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        return thread

    def skip_verification(self) -> bool:
        """Cuenta el pedido y termina la espera."""
        _FakeRunner.skipped += 1
        self._done.set()
        return True


def test_compress_job_forwards_the_skip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """La compresión del pipeline pasa el pedido de saltar al runner y termina bien."""
    monkeypatch.setattr(compress, "ConversionRunner", _FakeRunner)
    requests = iter([False, True])
    control = compress.CompressControl(lambda: False, lambda: next(requests, False))
    job = ConversionJob(tmp_path, tmp_path, tmp_path / "x.ffpfsc")
    result = compress.compress_job(job, ConversionOptions(1, 1, True), lambda *_a: None, control)
    assert result.succeeded and _FakeRunner.skipped == 1
