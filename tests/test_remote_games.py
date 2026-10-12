from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FakeConsole
from ffpfsc_converter.domain.models import ConversionOptions
from ffpfsc_converter.domain.pipeline import PipelineChoice
from ffpfsc_converter.domain.pipeline_events import PipelineFinished, PipelineOptionsRequired
from ffpfsc_converter.domain.remote import ConsoleTarget, RemoteEntry
from ffpfsc_converter.domain.remote_events import RemoteListing, RemoteLz4Found
from ffpfsc_converter.infrastructure.ftp import FtpClient
from ffpfsc_converter.services.pipeline.plan import is_convertible
from ffpfsc_converter.services.pipeline.runner import Ps5ConversionPipeline
from ffpfsc_converter.services.remote_browser import RemoteBrowser
from ffpfsc_converter.services.remote_games import (
    ALREADY_LZ4_TEXT,
    looks_like_game,
    mark_lz4_games,
)
from ffpfsc_converter.ui.explorer import view_presenters as vp

pytestmark = pytest.mark.filterwarnings("ignore:write permissions:RuntimeWarning")


def _make_lz4(ftp_root: Path) -> None:
    """Convierte el juego de prueba en una carpeta LZ4 (con su índice de paquetes)."""
    (ftp_root / "data/homebrew/Juego/ampr_assets.index").write_bytes(b"AMPR")


def test_looks_like_game() -> None:
    """Son juegos las carpetas de homebrew o con Title ID; los archivos no."""
    assert looks_like_game(RemoteEntry("x", "/mnt/usb0/homebrew/x", True))
    assert looks_like_game(RemoteEntry("PPSA01234-app0", "/data/otros/PPSA01234-app0", True))
    assert not looks_like_game(RemoteEntry("etc", "/data/etc", True))
    assert not looks_like_game(RemoteEntry("a.ffpfsc", "/data/homebrew/a.ffpfsc", False))


def test_lz4_games_are_marked_and_cannot_be_replaced(ftp_server: int, ftp_root: Path) -> None:
    """Una carpeta con ampr_assets.index queda marcada como LZ4 y no se puede reemplazar."""
    _make_lz4(ftp_root)
    client = FtpClient(ConsoleTarget("127.0.0.1", ftp_server))
    client.connect()
    try:
        entries = client.list_dir("/data/homebrew")
        marked = mark_lz4_games(client, entries, lambda: False)
        assert mark_lz4_games(client, entries, lambda: True) is None  # se dejó de revisar
    finally:
        client.close()
    assert marked is not None
    game = next(e for e in marked if e.name == "Juego")
    assert game.is_lz4 and vp.entry_badge(game) == vp.Badge("LZ4", "ok")
    assert not is_convertible(game) and not vp.action_states(True, False, [game]).convert


def test_browser_reports_lz4_games_after_the_listing(ftp_server: int, ftp_root: Path) -> None:
    """Primero se muestra la carpeta y después llega qué juegos están en LZ4."""
    _make_lz4(ftp_root)
    events: list[object] = []
    browser = RemoteBrowser(events.append)
    browser.connect(ConsoleTarget("127.0.0.1", ftp_server))
    browser.wait_idle()
    kinds = [type(e) for e in events]
    assert kinds.index(RemoteListing) < kinds.index(RemoteLz4Found)
    found = next(e for e in events if isinstance(e, RemoteLz4Found))
    assert [e.name for e in found.entries if e.is_lz4] == ["Juego"]
    browser.disconnect()
    browser.wait_idle()


def test_pipeline_refuses_an_lz4_folder(writable_ftp: int, ftp_root: Path,
                                        tmp_path: Path) -> None:
    """Aunque se pida igual, no descarga ni toca una carpeta que ya está en LZ4."""
    _make_lz4(ftp_root)
    console, events = FakeConsole(ftp_root, writable_ftp, usable=10**9), []
    choice = PipelineChoice(ConversionOptions(3, 1, False), delete_local=True)

    def emit(event: object) -> None:
        """Registra el evento y contesta la ventana de compresión."""
        events.append(event)
        if isinstance(event, PipelineOptionsRequired):
            pipeline.answer(choice)

    pipeline = Ps5ConversionPipeline(emit, console)  # type: ignore[arg-type]
    entry = RemoteEntry("Juego", "/data/homebrew/Juego", True)
    pipeline.start(entry, ConsoleTarget("127.0.0.1", writable_ftp), ["Juego"],
                   tmp_path / "work").join(20)
    result = events[-1].result
    assert isinstance(events[-1], PipelineFinished) and not result.succeeded
    assert ALREADY_LZ4_TEXT in result.message
    assert not (tmp_path / "work").exists() and console.modes == []
