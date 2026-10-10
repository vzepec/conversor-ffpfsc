from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

import pytest

from ffpfsc_converter.domain.remote import DownloadJob, FileTransfer, RemoteEntry
from ffpfsc_converter.services.file_download import download_file
from ffpfsc_converter.services.progress_meter import ProgressMeter
from ffpfsc_converter.services.resume_writer import OversizeDownloadError, ResumeMismatchError

#: Contenido sin repeticiones, para que un desplazamiento equivocado se note.
DATA = bytes((i * 7 + i // 251) % 256 for i in range(300_000))
BLOCK = 8192


class _Server:
    """Cliente remoto falso que sirve ``DATA`` en bloques.

    Attributes:
        honors_rest (bool): ``False`` imita a ps5upload: acepta REST pero envía desde 0.
        extra (bytes): Datos de más que envía al final (servidor que no se detiene).
        offsets (list[int]): Desplazamientos pedidos en cada descarga.
    """

    def __init__(self, honors_rest: bool = True, extra: bytes = b"") -> None:
        """Configura el comportamiento del servidor falso."""
        self.honors_rest, self.extra = honors_rest, extra
        self.offsets: list[int] = []

    def download(self, remote_path: str, sink: BinaryIO, offset: int,
                 on_chunk: Callable[[int], None]) -> None:
        """Envía el archivo desde el desplazamiento (o desde 0 si ignora REST)."""
        self.offsets.append(offset)
        payload = (DATA[offset:] if self.honors_rest else DATA) + self.extra
        for start in range(0, len(payload), BLOCK):
            block = payload[start:start + BLOCK]
            sink.write(block)
            on_chunk(len(block))


def _download(tmp_path: Path, server: _Server, partial: bytes | None) -> tuple[Path, DownloadJob]:
    """Descarga ``DATA`` con un ``.part`` previo opcional y devuelve el archivo y el trabajo."""
    final = tmp_path / "juego.ucas"
    if partial is not None:
        (tmp_path / "juego.ucas.part").write_bytes(partial)
    job = DownloadJob(RemoteEntry("juego.ucas", "/data/juego.ucas", False, len(DATA)), tmp_path,
                      total_bytes=len(DATA))
    meter = ProgressMeter(job, lambda _e: None)
    download_file(server, FileTransfer("/data/juego.ucas", final, len(DATA)),  # type: ignore[arg-type]
                  meter, lambda: False)
    return final, job


def test_resume_continues_when_server_honors_rest(tmp_path: Path) -> None:
    """Continúa desde el .part pidiendo solo un pequeño solapamiento para verificarlo."""
    server = _Server()
    final, job = _download(tmp_path, server, DATA[:200_000])
    assert final.read_bytes() == DATA
    assert 0 < server.offsets[0] < 200_000
    assert job.done_bytes == len(DATA)


def test_resume_restarts_when_server_ignores_rest(tmp_path: Path) -> None:
    """Si la PS5 envía desde el principio, reescribe el archivo en vez de pegarlo detrás."""
    final, job = _download(tmp_path, _Server(honors_rest=False), DATA[:200_000])
    assert final.read_bytes() == DATA
    assert job.done_bytes == len(DATA)


def test_corrupted_partial_is_discarded(tmp_path: Path) -> None:
    """Un .part que no coincide con la PS5 se borra para empezar de cero en el reintento."""
    with pytest.raises(ResumeMismatchError):
        _download(tmp_path, _Server(), bytes(200_000))
    assert not (tmp_path / "juego.ucas.part").exists()


def test_never_writes_past_the_expected_size(tmp_path: Path) -> None:
    """Corta la descarga si el servidor envía más bytes de los que informó."""
    with pytest.raises(OversizeDownloadError):
        _download(tmp_path, _Server(extra=b"x" * 50_000), None)
    assert not (tmp_path / "juego.ucas.part").exists()
    assert not (tmp_path / "juego.ucas").exists()


def test_meter_rewind_keeps_progress_consistent() -> None:
    """Descontar bytes omitidos deja el avance como si nunca se hubieran contado."""
    job = DownloadJob(RemoteEntry("a", "/a", False, 100), Path("."), total_bytes=100)
    meter = ProgressMeter(job, lambda _e: None)
    meter.skip(60)
    meter.rewind(60)
    meter.advance(100, "a")
    assert job.done_bytes == 100
