from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from ffpfsc_converter.config import LZ4_VERIFY_PHASE
from ffpfsc_converter.domain.events import JobFinished, JobProgress
from ffpfsc_converter.infrastructure.mkpfs_adapter import PackProcess
from ffpfsc_converter.services.conversion import ConversionRunner
from ffpfsc_converter.services.discovery import create_job
from ffpfsc_converter.services.lz4_local_steps import SKIPPED_TEXT, installed_components
from test_lz4_local import LZ4, _game


class _EndlessVerify:
    """Verificación falsa que no termina hasta que la detienen (como una muy larga)."""

    def __init__(self) -> None:
        """Empieza en marcha."""
        self._stop = threading.Event()

    def lines(self) -> Iterator[str]:
        """Espera a que la terminen sin escribir nada."""
        self._stop.wait(30)
        yield from ()

    def wait(self) -> int:
        """Devuelve el código de un proceso terminado a la fuerza."""
        return -15

    def terminate(self) -> None:
        """Detiene la espera."""
        self._stop.set()


@pytest.mark.skipif(installed_components() is None, reason="sin componentes de ampr_emu")
def test_verification_can_be_skipped_while_running(tmp_path: Path) -> None:
    """Saltar la verificación en curso deja la carpeta LZ4 lista (no es una cancelación)."""
    job = create_job(_game(tmp_path / "PPSA01234"))
    events: list[object] = []
    runner: ConversionRunner

    def record(event: object) -> None:
        """Registra el evento y, al empezar la verificación, pide saltarla."""
        events.append(event)
        if isinstance(event, JobProgress) and event.progress.phase == LZ4_VERIFY_PHASE:
            threading.Timer(0.2, runner.skip_verification).start()

    def factory(command: list[str]) -> object:
        """Usa las herramientas reales salvo en la verificación."""
        return _EndlessVerify() if "verify" in command else PackProcess(command)

    runner = ConversionRunner(record, factory)  # type: ignore[arg-type]
    assert not runner.skip_verification()  # sin verificación en curso no hace nada
    runner.start([job], LZ4).join(timeout=300)
    finished = next(e for e in events if isinstance(e, JobFinished))
    assert finished.result.succeeded and not finished.result.cancelled
    assert job.output.is_dir() and (job.output / "ampr_assets.index").exists()
    assert any(getattr(e, "text", "") == SKIPPED_TEXT for e in events)
