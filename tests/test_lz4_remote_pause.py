from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ffpfsc_converter.config import E2A_PAUSED_GAME_CODE
from ffpfsc_converter.domain.lz4 import Lz4JobState, Lz4Request
from ffpfsc_converter.domain.lz4_events import Lz4Finished, Lz4Progress, Lz4Started
from ffpfsc_converter.services.lz4_watch import is_ongoing, resumes_by_itself
from lz4_fake_client import GAME, HOST, FakeEngine, make_harness, status

_JOIN = 5
REQUEST = Lz4Request(GAME, "/data/homebrew", level=9, verify=True, remove_source=False)
RUNNING = status(Lz4JobState.RUNNING, 50)
DONE = status(Lz4JobState.DONE, 100)
GAME_PAUSE = replace(status(Lz4JobState.PAUSED, 50), code=E2A_PAUSED_GAME_CODE, resumable=True)
USER_PAUSE = replace(status(Lz4JobState.PAUSED, 50), code="paused_user", resumable=True)


def test_game_pause_resumes_by_itself() -> None:
    """Solo la pausa por abrir el juego se considera pendiente de reanudarse sola."""
    assert resumes_by_itself(GAME_PAUSE) and is_ongoing(GAME_PAUSE)
    assert not resumes_by_itself(USER_PAUSE) and not is_ongoing(USER_PAUSE)
    full = replace(USER_PAUSE, code="paused_full")
    assert not is_ongoing(full) and is_ongoing(RUNNING) and not is_ongoing(DONE)


def test_game_pause_keeps_following_until_done(tmp_path: Path) -> None:
    """La pausa por abrir el juego se publica como avance y el seguimiento continúa."""
    engine = FakeEngine(states=[RUNNING, GAME_PAUSE, GAME_PAUSE, RUNNING, DONE])
    harness = make_harness(tmp_path, engine)
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert harness.kinds() == [Lz4Started, *[Lz4Progress] * 4, Lz4Finished]
    assert harness.events[2] == Lz4Progress(HOST, GAME_PAUSE)
    assert harness.events[-1] == Lz4Finished(HOST, DONE)
    assert not harness.remote.busy


def test_game_pause_right_after_start_is_followed(tmp_path: Path) -> None:
    """Una pausa por el juego sin haber visto la conversión en marcha no la termina."""
    harness = make_harness(tmp_path, FakeEngine(states=[GAME_PAUSE, RUNNING, DONE]))
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert harness.kinds() == [Lz4Started, Lz4Progress, Lz4Progress, Lz4Finished]


def test_manual_pause_ends_following(tmp_path: Path) -> None:
    """Las pausas que hay que reanudar a mano terminan el seguimiento con ``Lz4Finished``."""
    for code in ("paused_user", "paused_full", "paused_dest", "paused_source"):
        paused = replace(USER_PAUSE, code=code)
        harness = make_harness(tmp_path / code, FakeEngine(states=[RUNNING, paused]))
        harness.remote.start(HOST, REQUEST).join(_JOIN)
        assert harness.events[-1] == Lz4Finished(HOST, paused)


def test_watch_follows_game_pause(tmp_path: Path) -> None:
    """Al conectarse sigue una conversión que estaba en pausa por el juego abierto."""
    harness = make_harness(tmp_path, FakeEngine(states=[GAME_PAUSE, GAME_PAUSE, DONE]))
    harness.remote.watch(HOST).join(_JOIN)
    assert harness.kinds() == [Lz4Progress, Lz4Finished]
    assert harness.events[-1] == Lz4Finished(HOST, DONE)
