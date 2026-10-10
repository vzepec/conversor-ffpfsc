from __future__ import annotations

from pathlib import Path

import pytest

from ffpfsc_converter.domain.remote import (
    ConsoleTarget,
    DownloadJob,
    DownloadState,
    RemoteEntry,
)
from ffpfsc_converter.domain.remote_events import (
    DownloadFinished,
    DownloadProgress,
    DownloadQueueFinished,
    DownloadStarted,
)
from ffpfsc_converter.services import remote_download as downloads
from ffpfsc_converter.services.download_planner import local_name
from ffpfsc_converter.services.downloads import DownloadRunner

GAME = RemoteEntry("Juego", "/data/homebrew/Juego", True)
IMAGE = RemoteEntry("imagen.ffpfsc", "/data/homebrew/imagen.ffpfsc", False, 50_000)


def _run(port: int, jobs: list[DownloadJob]) -> list[object]:
    """Descarga los trabajos contra el FTP de prueba y devuelve los eventos."""
    events: list[object] = []
    DownloadRunner(events.append).start(jobs, ConsoleTarget("127.0.0.1", port)).join(10)
    return events


def test_downloads_folder_and_file(ftp_server: int, ftp_root: Path, tmp_path: Path) -> None:
    """Descarga una carpeta completa (incluida una vacía) y un archivo suelto."""
    dest = tmp_path / "descargas"
    jobs = [DownloadJob(GAME, dest), DownloadJob(IMAGE, dest)]
    events = _run(ftp_server, jobs)

    assert isinstance(events[0], DownloadStarted)
    assert any(isinstance(e, DownloadProgress) for e in events)
    assert events[-1] == DownloadQueueFinished(cancelled=False)
    assert all(j.state is DownloadState.SUCCEEDED for j in jobs)
    source = ftp_root / "data" / "homebrew"
    original = (source / "Juego" / "eboot.bin").read_bytes()
    assert (dest / "Juego" / "eboot.bin").read_bytes() == original
    assert (dest / "Juego" / "sce_sys" / "param.json").is_file()
    assert (dest / "Juego" / "vacia").is_dir()
    assert (dest / "imagen.ffpfsc").stat().st_size == 50_000
    assert jobs[0].done_bytes == jobs[0].total_bytes > 0
    assert not list(dest.rglob("*.part"))


def test_resumes_partial_and_skips_complete(ftp_server: int, tmp_path: Path) -> None:
    """Continúa un .part existente y no vuelve a bajar lo ya completo."""
    dest = tmp_path / "descargas"
    (dest / "Juego").mkdir(parents=True)
    (dest / "Juego" / "eboot.bin.part").write_bytes(b"E" * 100_000)
    (dest / "imagen.ffpfsc").write_bytes(b"F" * 50_000)
    jobs = [DownloadJob(GAME, dest), DownloadJob(IMAGE, dest)]
    events = _run(ftp_server, jobs)

    results = [e.result for e in events if isinstance(e, DownloadFinished)]
    assert all(r.succeeded for r in results)
    assert (dest / "Juego" / "eboot.bin").read_bytes() == b"E" * 300_000
    assert jobs[1].done_bytes == 50_000


def test_cancel_keeps_partial_for_later(ftp_server: int, tmp_path: Path) -> None:
    """Cancelar deja el estado cancelado y no inicia las descargas siguientes."""
    events: list[object] = []
    runner = DownloadRunner(events.append)
    runner.cancel()  # start() limpia una cancelación previa
    jobs = [DownloadJob(GAME, tmp_path), DownloadJob(IMAGE, tmp_path)]
    original = downloads.download_file

    def cancel_after_first(*args: object) -> None:
        """Descarga el primer archivo y luego pide cancelar."""
        original(*args)  # type: ignore[arg-type]
        runner.cancel()

    downloads.download_file = cancel_after_first  # type: ignore[assignment]
    try:
        runner.start(jobs, ConsoleTarget("127.0.0.1", ftp_server)).join(10)
    finally:
        downloads.download_file = original
    assert jobs[0].state is DownloadState.CANCELLED
    assert jobs[1].state is DownloadState.QUEUED
    assert events[-1] == DownloadQueueFinished(cancelled=True)


def test_not_enough_space(ftp_server: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Avisa antes de empezar si no cabe en el disco local."""
    monkeypatch.setattr(downloads, "free_space", lambda _d: 10)
    job = DownloadJob(IMAGE, tmp_path)
    events = _run(ftp_server, [job])
    result = next(e for e in events if isinstance(e, DownloadFinished)).result
    assert job.state is DownloadState.FAILED
    assert "No hay espacio suficiente" in result.message


def test_missing_remote_file_fails_with_message(ftp_server: int, tmp_path: Path) -> None:
    """Un archivo que ya no existe en la PS5 marca la descarga como fallida."""
    job = DownloadJob(RemoteEntry("x.bin", "/no/x.bin", False, 5), tmp_path)
    events = _run(ftp_server, [job])
    result = next(e for e in events if isinstance(e, DownloadFinished)).result
    assert job.state is DownloadState.FAILED and result.message


def test_local_name_is_valid_on_windows() -> None:
    """Reemplaza los caracteres que Windows no admite."""
    assert local_name('Juego: Edición "GOTY"?') == "Juego_ Edición _GOTY__"
    assert local_name("nombre. ") == "nombre"
    assert local_name("...") == "_"
