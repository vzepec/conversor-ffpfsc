"""Pruebas de punta a punta de la compresión LZ4 con el cliente HTTP real y un motor falso."""
from __future__ import annotations

from pathlib import Path

from e2a_fake_data import DEST_INTERNAL, GAME_NOT_AMPR, GAME_OK
from ffpfsc_converter.config import E2A_PAUSED_GAME_CODE
from ffpfsc_converter.domain.lz4 import Lz4JobState, Lz4Request, Lz4Status
from ffpfsc_converter.domain.lz4_events import (
    Lz4EngineLaunched,
    Lz4Finished,
    Lz4PairingRequired,
    Lz4Ready,
    Lz4Rejected,
    Lz4Started,
)
from ffpfsc_converter.services.lz4_watch import resumes_by_itself
from lz4_e2e_harness import ELF_BYTES, EVENT_TIMEOUT, E2eFlow, request_for, running_flow


def _is_running(status: Lz4Status) -> bool:
    """Indica si el estado corresponde a la conversión en marcha."""
    return status.state is Lz4JobState.RUNNING


def _start_game(flow: E2eFlow) -> Lz4Request:
    """Analiza el juego compatible, inicia su conversión y espera verla en marcha."""
    flow.remote.prepare(flow.host, GAME_OK.path)
    request = request_for(flow.expect(Lz4Ready).plan)
    flow.remote.start(flow.host, request)
    assert flow.expect(Lz4Started) == Lz4Started(flow.host, request, 0)
    flow.expect_progress(_is_running)
    return request


def _finish(flow: E2eFlow) -> Lz4Status:
    """Lleva la conversión al 100 % y devuelve el resultado publicado."""
    flow.engine.advance(100)
    return flow.expect(Lz4Finished).status


def test_launch_pair_and_convert(tmp_path: Path) -> None:
    """Con el motor apagado envía el ELF, empareja (tras un código malo) y convierte."""
    with running_flow(tmp_path) as flow:
        flow.remote.prepare(flow.host, GAME_OK.path)
        assert flow.expect(Lz4EngineLaunched) == Lz4EngineLaunched(flow.host)
        assert flow.loader.wait() == ELF_BYTES
        assert flow.expect(Lz4PairingRequired) == Lz4PairingRequired(flow.host, GAME_OK.path)
        flow.remote.pair(flow.host, "000000", GAME_OK.path)
        assert flow.expect(Lz4PairingRequired).retry
        assert flow.settings.token(flow.host) is None
        flow.remote.pair(flow.host, flow.engine.pin, GAME_OK.path)
        plan = flow.expect(Lz4Ready).plan
        assert flow.settings.token(flow.host) in flow.engine.tokens
        assert plan.source.title_id == GAME_OK.title_id and not plan.check.is_blocked
        assert plan.dest_base == DEST_INTERNAL.base
        request = request_for(plan)
        thread = flow.remote.start(flow.host, request)
        assert flow.expect(Lz4Started).position == 0
        flow.expect_progress(_is_running)
        flow.engine.advance(60)
        flow.expect_progress(lambda status: status.percent == 60)
        result = _finish(flow)
        thread.join(EVENT_TIMEOUT)
        assert result.state is Lz4JobState.DONE and result.dest == request.output_path
        assert not flow.remote.busy
        sent = flow.engine.last("/api/start").params
        assert (sent["path"], sent["dest"]) == (GAME_OK.path, DEST_INTERNAL.base)
        assert (sent["level"], sent["verify"], sent["remove"]) == ("9", "1", "0")


def test_cancel_ends_with_cancelled(tmp_path: Path) -> None:
    """Cancelar desde la app termina el seguimiento con el resultado ``cancelled``."""
    with running_flow(tmp_path, is_engine_up=True, is_paired=True) as flow:
        request = _start_game(flow)
        flow.remote.cancel(flow.host)
        result = flow.expect(Lz4Finished).status
        assert result.state is Lz4JobState.CANCELLED
        assert request.output_path not in flow.engine.console.existing
        assert "/api/cancel" in flow.engine.paths() and flow.loader.received == []


def test_manual_pause_and_resume(tmp_path: Path) -> None:
    """La pausa manual termina el seguimiento y «Reanudar» lo retoma hasta el final."""
    with running_flow(tmp_path, is_engine_up=True, is_paired=True) as flow:
        request = _start_game(flow)
        flow.remote.pause(flow.host)
        paused = flow.expect(Lz4Finished).status
        assert paused.state is Lz4JobState.PAUSED and paused.code == "paused_user"
        assert paused.resumable and paused.dest == request.output_path
        flow.remote.resume(flow.host, paused.dest)
        flow.expect_progress(_is_running)
        assert flow.engine.last("/api/resume").params["dest"] == request.output_path
        assert _finish(flow).state is Lz4JobState.DONE


def test_not_ampr_is_rejected(tmp_path: Path) -> None:
    """Un juego sin ``libSceAmpr`` se analiza, pero la comprobación final lo rechaza."""
    with running_flow(tmp_path, is_engine_up=True, is_paired=True) as flow:
        flow.remote.prepare(flow.host, GAME_NOT_AMPR.path)
        plan = flow.expect(Lz4Ready).plan
        assert plan.check.errors == ("not_ampr",)
        flow.remote.start(flow.host, request_for(plan)).join(EVENT_TIMEOUT)
        assert flow.expect(Lz4Rejected).check.errors == ("not_ampr",)
        assert "/api/start" not in flow.engine.paths()


def test_game_pause_resumes_by_itself(tmp_path: Path) -> None:
    """Abrir el juego pausa la conversión sin terminar el seguimiento; al cerrarlo, sigue."""
    with running_flow(tmp_path, is_engine_up=True, is_paired=True) as flow:
        _start_game(flow)
        flow.engine.open_game()
        waiting = flow.expect_progress(resumes_by_itself).status
        assert waiting.code == E2A_PAUSED_GAME_CODE
        flow.engine.close_game()
        flow.expect_progress(_is_running)
        assert _finish(flow).state is Lz4JobState.DONE
        assert "/api/resume" not in flow.engine.paths()
