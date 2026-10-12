"""Tests de E2aClient contra el exfat2ampr falso: estado y control de la conversión."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from e2a_fake import FakeE2aEngine
from e2a_fake_data import DEST_INTERNAL, GAME_NOT_AMPR, GAME_OK
from ffpfsc_converter.domain.lz4 import Lz4JobState, Lz4Request
from ffpfsc_converter.infrastructure.exfat2ampr import E2aClient, E2aHttpError

TIMEOUT = 2.0
OUTPUT = f"{DEST_INTERNAL.base}/{GAME_OK.title_id}-LZ4"


@pytest.fixture
def engine() -> Iterator[FakeE2aEngine]:
    """exfat2ampr falso en marcha."""
    fake = FakeE2aEngine().start()
    yield fake
    fake.stop()


@pytest.fixture
def client(engine: FakeE2aEngine) -> E2aClient:
    """Cliente ya emparejado con el motor falso."""
    return E2aClient(engine.host, engine.issue_token(), port=engine.port, timeout=TIMEOUT)


def _start(client: E2aClient) -> Lz4Request:
    """Pide la conversión del juego compatible al almacenamiento interno."""
    source = next(s for s in client.sources() if s.path == GAME_OK.path)
    request = Lz4Request(source, DEST_INTERNAL.base, level=9, verify=True, remove_source=False,
                         name=f"{GAME_OK.title_id}-LZ4")
    client.start(request)
    return request


def test_output_over_the_original_fails_without_deleting(engine: FakeE2aEngine,
                                                         client: E2aClient) -> None:
    """Si ``<destino>/<TITLE_ID>`` es el propio juego, el motor falla con ``dest_is_source``."""
    source = next(s for s in client.sources() if s.path == GAME_OK.path)
    client.start(Lz4Request(source, DEST_INTERNAL.base, 9, True, False))
    status = client.state()
    assert status.state is Lz4JobState.ERROR and status.code == "dest_is_source"
    assert GAME_OK.path in engine.console.games


def test_state_idle_then_running(engine: FakeE2aEngine, client: E2aClient) -> None:
    """Sin conversiones el estado es idle; tras ``start`` corre y avanza."""
    assert client.state().state is Lz4JobState.IDLE
    request = _start(client)
    running = client.state()
    assert running.state is Lz4JobState.RUNNING and running.is_active
    assert running.dest == request.output_path == OUTPUT
    engine.advance(40)
    status = client.state()
    assert status.percent == 40 and status.eta_seconds == 60
    assert status.bytes_done == GAME_OK.size * 40 // 100


def test_state_shows_previous_result_right_after_start(
        engine: FakeE2aEngine, client: E2aClient) -> None:
    """Justo tras ``start`` puede verse todavía el resultado de la conversión anterior."""
    engine.seed_result(GAME_NOT_AMPR, "error", "not_ampr")
    engine.jobs.stale_polls = 2
    _start(client)
    for _ in range(2):
        stale = client.state()
        assert (stale.state, stale.title_id, stale.code) == (
            Lz4JobState.ERROR, GAME_NOT_AMPR.title_id, "not_ampr")
    fresh = client.state()
    assert (fresh.state, fresh.title_id) == (Lz4JobState.RUNNING, GAME_OK.title_id)


def test_finish_done_keeps_result(engine: FakeE2aEngine, client: E2aClient) -> None:
    """Al terminar, el estado queda en done hasta ``dismiss`` y la salida ya existe."""
    _start(client)
    engine.finish("done")
    assert client.state().state is Lz4JobState.DONE
    assert client.state().percent == 100
    assert OUTPUT in engine.console.existing
    client.dismiss()
    assert client.state().state is Lz4JobState.IDLE


def test_auto_step_advances_per_poll(engine: FakeE2aEngine, client: E2aClient) -> None:
    """Con ``auto_step`` la conversión avanza en cada consulta hasta terminar."""
    engine.jobs.auto_step = 50
    _start(client)
    assert client.state().percent == 50
    assert client.state().state is Lz4JobState.DONE


def test_pause_and_resume(engine: FakeE2aEngine, client: E2aClient) -> None:
    """La pausa deja un punto de reanudación; reanudar exige la carpeta de salida."""
    _start(client)
    engine.advance(30)
    client.pause()
    paused = client.state()
    assert paused.state is Lz4JobState.PAUSED and paused.resumable
    with pytest.raises(E2aHttpError) as wrong:
        client.resume("/data/homebrew/OTRO")
    assert wrong.value.status == 400 and wrong.value.error == "cannot resume"
    client.resume(OUTPUT)
    assert engine.last("/api/resume").params == {"dest": OUTPUT}
    resumed = client.state()
    assert resumed.state is Lz4JobState.RUNNING and resumed.percent == 30


def test_cancel_retry_and_dismiss(engine: FakeE2aEngine, client: E2aClient) -> None:
    """Cancelar deja el resultado cancelled; se puede repetir y no descartar mientras corre."""
    _start(client)
    client.cancel()
    assert client.state().state is Lz4JobState.CANCELLED
    client.retry()
    assert client.state().state is Lz4JobState.RUNNING
    with pytest.raises(E2aHttpError) as busy:
        client.dismiss()
    assert (busy.value.status, busy.value.code) == (409, "busy")
    engine.finish("done")
    with pytest.raises(E2aHttpError) as nothing:
        client.retry()
    assert (nothing.value.status, nothing.value.code) == (409, "nothing_to_retry")
