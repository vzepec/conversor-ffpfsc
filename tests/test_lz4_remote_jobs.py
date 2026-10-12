from __future__ import annotations

import threading
import time
from dataclasses import replace
from pathlib import Path

from ffpfsc_converter.config import E2A_POLL_MAX_FAILURES, E2A_STALE_GRACE_SECONDS
from ffpfsc_converter.domain.lz4 import Lz4JobState, Lz4Request
from ffpfsc_converter.domain.lz4_events import (
    Lz4Failed,
    Lz4Finished,
    Lz4PairingRequired,
    Lz4Progress,
    Lz4Rejected,
    Lz4Started,
)
from ffpfsc_converter.infrastructure.exfat2ampr import E2aHttpError
from lz4_fake_client import GAME, HOST, OK_CHECK, FakeEngine, make_harness, status

_JOIN = 5
REQUEST = Lz4Request(GAME, "/data/homebrew", level=9, verify=True, remove_source=False)
RUNNING = status(Lz4JobState.RUNNING, 50)
DONE = status(Lz4JobState.DONE, 100)


def _finished(events: list[object]) -> Lz4Finished:
    """Devuelve el único ``Lz4Finished`` publicado."""
    finished = [e for e in events if isinstance(e, Lz4Finished)]
    assert len(finished) == 1
    return finished[0]


def test_blocked_check_rejects_without_starting(tmp_path: Path) -> None:
    """Si la comprobación final tiene errores, publica ``Lz4Rejected`` y no inicia."""
    blocked = replace(OK_CHECK, errors=("space_insufficient",))
    harness = make_harness(tmp_path, FakeEngine(check_result=blocked))
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert harness.events == [Lz4Rejected(HOST, blocked)]
    assert "start" not in harness.engine.calls


def test_start_follows_until_done(tmp_path: Path) -> None:
    """Una conversión aceptada publica inicio, avance y resultado."""
    engine = FakeEngine(states=[status(Lz4JobState.RUNNING, 10), RUNNING, DONE])
    harness = make_harness(tmp_path, engine)
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert harness.kinds() == [Lz4Started, Lz4Progress, Lz4Progress, Lz4Finished]
    assert harness.events[0] == Lz4Started(HOST, REQUEST, 0)
    assert _finished(harness.events).status == DONE
    assert not harness.remote.busy


def test_previous_result_does_not_end_tracking(tmp_path: Path) -> None:
    """El resultado anterior que aún muestra exfat2ampr no termina el seguimiento."""
    previous_other = status(Lz4JobState.DONE, 100, title_id="PPSA09999", dest="/data/homebrew/X")
    previous_same = status(Lz4JobState.ERROR, 3)
    engine = FakeEngine(states=[previous_other, previous_same, RUNNING, DONE])
    harness = make_harness(tmp_path, engine)
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert harness.kinds() == [Lz4Started, Lz4Progress, Lz4Finished]
    assert _finished(harness.events).status == DONE


def test_fast_job_ends_after_grace(tmp_path: Path) -> None:
    """Si nunca se ve en marcha, acepta su resultado tras el margen de seguridad."""
    harness = make_harness(tmp_path, FakeEngine(states=[DONE]))
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert _finished(harness.events).status == DONE
    assert harness.clock.now >= E2A_STALE_GRACE_SECONDS


def test_brief_network_failures_are_tolerated(tmp_path: Path) -> None:
    """Unos pocos fallos de red seguidos no interrumpen el seguimiento."""
    cuts: list[object] = [TimeoutError()] * (E2A_POLL_MAX_FAILURES - 1)
    engine = FakeEngine(states=[RUNNING, *cuts, RUNNING, DONE])  # type: ignore[list-item]
    harness = make_harness(tmp_path, engine)
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert harness.kinds() == [Lz4Started, Lz4Progress, Lz4Progress, Lz4Finished]


def test_lost_connection_fails(tmp_path: Path) -> None:
    """Demasiados fallos de red seguidos terminan con ``Lz4Failed``."""
    engine = FakeEngine(states=[RUNNING, ConnectionResetError()])
    harness = make_harness(tmp_path, engine)
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert harness.kinds() == [Lz4Started, Lz4Progress, Lz4Failed]
    assert "sigue en la PS5" in harness.events[-1].message  # type: ignore[attr-defined]
    assert harness.engine.calls.count("state") == 1 + E2A_POLL_MAX_FAILURES


def test_rejected_token_asks_to_pair_again(tmp_path: Path) -> None:
    """Un 401 durante el uso olvida el token y pide emparejar de nuevo."""
    harness = make_harness(tmp_path, FakeEngine(tokens={"otro"}))
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert harness.events == [Lz4PairingRequired(HOST, GAME.path)]
    assert harness.settings.token(HOST) is None


def test_engine_rejection_is_translated(tmp_path: Path) -> None:
    """Un error de exfat2ampr al iniciar se muestra en español."""
    engine = FakeEngine(start_error=E2aHttpError(409, "queue_full", "queue full"))
    harness = make_harness(tmp_path, engine)
    harness.remote.start(HOST, REQUEST).join(_JOIN)
    assert harness.kinds() == [Lz4Failed]
    assert "en espera" in harness.events[0].message  # type: ignore[attr-defined]


def test_pause_and_cancel_send_orders(tmp_path: Path) -> None:
    """Pausar y cancelar envían la orden sin publicar eventos si sale bien."""
    harness = make_harness(tmp_path)
    harness.remote.pause(HOST).join(_JOIN)
    harness.remote.cancel(HOST).join(_JOIN)
    assert harness.engine.calls == ["pause", "cancel"]
    assert harness.events == []


def test_order_with_engine_down_fails(tmp_path: Path) -> None:
    """Una orden que no llega al motor se publica como ``Lz4Failed``."""
    harness = make_harness(tmp_path, FakeEngine(is_up=False))
    harness.remote.cancel(HOST).join(_JOIN)
    assert harness.kinds() == [Lz4Failed]


def test_resume_follows_again(tmp_path: Path) -> None:
    """Reanudar ignora la pausa anterior y sigue la conversión hasta el final."""
    paused = status(Lz4JobState.PAUSED, 40)
    harness = make_harness(tmp_path, FakeEngine(states=[paused, RUNNING, DONE]))
    harness.remote.resume(HOST, "/data/homebrew/PPSA01234/").join(_JOIN)
    assert harness.engine.calls[0] == "resume /data/homebrew/PPSA01234/"
    assert harness.kinds() == [Lz4Progress, Lz4Finished]


def test_watch_follows_active_job(tmp_path: Path) -> None:
    """Al conectarse sigue la conversión que ya estaba en marcha."""
    harness = make_harness(tmp_path, FakeEngine(states=[RUNNING, RUNNING, DONE]))
    harness.remote.watch(HOST).join(_JOIN)
    assert harness.kinds() == [Lz4Progress, Lz4Finished]
    assert _finished(harness.events).status == DONE


def test_watch_is_silent_when_idle_down_or_unpaired(tmp_path: Path) -> None:
    """Sin conversión activa, sin motor o sin token, ``watch`` no publica nada."""
    idle = make_harness(tmp_path / "a", FakeEngine(states=[DONE]))
    idle.remote.watch(HOST).join(_JOIN)
    down = make_harness(tmp_path / "b", FakeEngine(is_up=False))
    down.remote.watch(HOST).join(_JOIN)
    unpaired = make_harness(tmp_path / "c", FakeEngine(states=[RUNNING]))
    unpaired.settings.forget_token(HOST)
    unpaired.remote.watch(HOST).join(_JOIN)
    assert idle.events == down.events == unpaired.events == []
    assert unpaired.engine.calls == []


def test_busy_while_tracking(tmp_path: Path) -> None:
    """El servicio está ocupado desde que se pide la conversión hasta que termina."""
    gate = threading.Event()
    harness = make_harness(tmp_path, FakeEngine(states=[RUNNING, DONE], state_gate=gate))
    thread = harness.remote.start(HOST, REQUEST)
    assert harness.remote.busy
    gate.set()
    thread.join(_JOIN)
    assert not harness.remote.busy


def test_stop_watching_ends_tracking(tmp_path: Path) -> None:
    """Dejar de seguir termina el hilo aunque la conversión continúe."""
    harness = make_harness(tmp_path, FakeEngine(states=[RUNNING]))
    thread = harness.remote.watch(HOST)
    deadline = time.monotonic() + _JOIN
    while harness.engine.calls.count("state") < 3 and time.monotonic() < deadline:
        time.sleep(0.001)
    harness.remote.stop_watching()
    thread.join(_JOIN)
    assert not thread.is_alive()
    assert not harness.remote.busy
