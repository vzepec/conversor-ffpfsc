from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.domain.events import JobInfoReady, JobSizeReady
from ffpfsc_converter.services.analysis import analyze_job
from ffpfsc_converter.services.discovery import create_job


def test_compressed_file_is_measured_but_not_estimated(tmp_path: Path) -> None:
    """De un .ffpfsc se leen el nombre y el tamaño, pero no se estima (ya está comprimido)."""
    ready = tmp_path / "Juego.ffpfsc"
    ready.write_bytes(b"P" * 4096)
    job = create_job(ready)
    events: list[object] = []
    analyze_job(job, [3, 9], events.append)
    assert [type(e) for e in events] == [JobInfoReady, JobSizeReady]
    assert job.size == 4096 and job.estimates == {}
