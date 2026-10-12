"""Tests de E2aClient contra el exfat2ampr falso: emparejamiento, consultas y órdenes."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from e2a_fake import FakeE2aEngine
from e2a_fake_data import DEST_INTERNAL, DEST_USB, GAME_IMAGE, GAME_NOT_AMPR, GAME_OK
from ffpfsc_converter.domain.lz4 import Lz4Compat, Lz4Request, Lz4Source
from ffpfsc_converter.infrastructure.exfat2ampr import E2aClient, E2aHttpError

TIMEOUT = 2.0


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


def _source(client: E2aClient, path: str) -> Lz4Source:
    """Busca un juego por su ruta en ``/api/sources``."""
    return next(s for s in client.sources() if s.path == path)


def test_hello_reports_pairing(engine: FakeE2aEngine, client: E2aClient) -> None:
    """``hello`` funciona sin token e indica si el token es válido."""
    anonymous = E2aClient(engine.host, port=engine.port, timeout=TIMEOUT)
    assert anonymous.hello().paired is False
    info = client.hello()
    assert info.paired and info.version == "1.45"


def test_pair_returns_working_token(engine: FakeE2aEngine) -> None:
    """Con el código correcto devuelve un token que abre las rutas protegidas."""
    token = E2aClient(engine.host, port=engine.port, timeout=TIMEOUT).pair("123456")
    assert len(token) == 32
    paired = E2aClient(engine.host, token, port=engine.port, timeout=TIMEOUT)
    assert paired.hello().paired
    assert paired.sources()
    assert engine.last("/api/sources").token == token
    assert engine.last("/api/pair").params == {"pin": "123456"}


def test_pair_bad_code_and_block(engine: FakeE2aEngine) -> None:
    """Un código malo da 403; el quinto fallo y los siguientes intentos dan 429."""
    anonymous = E2aClient(engine.host, port=engine.port, timeout=TIMEOUT)
    for _ in range(4):
        with pytest.raises(E2aHttpError) as bad:
            anonymous.pair("000000")
        assert bad.value.status == 403 and bad.value.error == "bad code"
    for pin in ("000000", "123456"):
        with pytest.raises(E2aHttpError) as blocked:
            anonymous.pair(pin)
        assert blocked.value.status == 429 and blocked.value.code == "blocked"


def test_pair_after_block_needs_new_code(engine: FakeE2aEngine) -> None:
    """Tras el bloqueo el código cambia: el anterior ya no sirve."""
    engine.block_seconds = 0
    anonymous = E2aClient(engine.host, port=engine.port, timeout=TIMEOUT)
    for _ in range(5):
        with pytest.raises(E2aHttpError):
            anonymous.pair("000000")
    with pytest.raises(E2aHttpError) as old:
        anonymous.pair("123456")
    assert old.value.status == 403
    assert anonymous.pair(engine.next_pin)


@pytest.mark.parametrize("token", [None, "f" * 32])
def test_protected_routes_need_token(engine: FakeE2aEngine, token: str | None) -> None:
    """Sin token o con uno inválido el motor responde 401 ``pair``."""
    anonymous = E2aClient(engine.host, token, port=engine.port, timeout=TIMEOUT)
    with pytest.raises(E2aHttpError) as unauthorized:
        anonymous.sources()
    assert (unauthorized.value.status, unauthorized.value.code) == (401, "pair")


def test_sources_and_destinations(client: E2aClient) -> None:
    """Lista los juegos (carpeta e imagen) y las unidades con su espacio."""
    sources = {s.path: s for s in client.sources()}
    assert set(sources) == {GAME_OK.path, GAME_NOT_AMPR.path, GAME_IMAGE.path}
    assert sources[GAME_IMAGE.path].is_image
    assert sources[GAME_IMAGE.path].smp_title == GAME_IMAGE.smp_title
    assert sources[GAME_OK.path].title_id == "PPSA01234"
    destinations = {d.base: d for d in client.destinations()}
    assert destinations[DEST_INTERNAL.base].free == DEST_INTERNAL.free
    assert destinations[DEST_USB.base].kind == "usb" and destinations[DEST_USB.base].index == 0


def test_check_ok_and_blocked(engine: FakeE2aEngine, client: E2aClient) -> None:
    """La comprobación previa refleja compatibilidad, espacio y salida existente."""
    ok = client.check(_source(client, GAME_OK.path), DEST_INTERNAL.base)
    assert ok.compatible is Lz4Compat.YES and not ok.is_blocked
    assert ok.source_bytes == GAME_OK.size
    assert "smp" not in engine.last("/api/check").params
    assert client.check(_source(client, GAME_NOT_AMPR.path), DEST_INTERNAL.base).errors == \
        ("not_ampr",)
    assert "space_insufficient" in client.check(_source(client, GAME_OK.path), DEST_USB.base).errors
    engine.console.existing.add(f"{DEST_INTERNAL.base}/{GAME_OK.title_id}")
    again = client.check(_source(client, GAME_OK.path), DEST_INTERNAL.base)
    assert again.warnings == ("already_exists",)


def test_check_image_sends_mount_title(engine: FakeE2aEngine, client: E2aClient) -> None:
    """En imágenes se envía ``smp`` con el Title ID de montaje."""
    check = client.check(_source(client, GAME_IMAGE.path), DEST_INTERNAL.base)
    assert check.compatible is Lz4Compat.LATER
    assert engine.last("/api/check").params == {
        "path": GAME_IMAGE.path, "dest": DEST_INTERNAL.base, "smp": GAME_IMAGE.smp_title}


def test_start_sends_form_fields(engine: FakeE2aEngine, client: E2aClient) -> None:
    """``start`` manda ruta, destino, nivel y flags «1»/«0» con el token."""
    request = Lz4Request(_source(client, GAME_OK.path), DEST_INTERNAL.base, level=12,
                         verify=True, remove_source=False, overwrite=True)
    assert client.start(request) == 0
    sent = engine.last("/api/start")
    assert sent.method == "POST" and sent.token
    assert sent.params == {"path": GAME_OK.path, "dest": DEST_INTERNAL.base, "level": "12",
                           "verify": "1", "remove": "0", "overwrite": "1"}


def test_start_image_and_queue(engine: FakeE2aEngine, client: E2aClient) -> None:
    """Una imagen manda ``smp``; con una conversión en curso la nueva queda en cola."""
    client.start(Lz4Request(_source(client, GAME_OK.path), DEST_INTERNAL.base, 9, True, False))
    image = Lz4Request(_source(client, GAME_IMAGE.path), DEST_INTERNAL.base, 1, False, True)
    assert client.start(image) == 1
    assert engine.last("/api/start").params["smp"] == GAME_IMAGE.smp_title
    assert client.state().queue == (GAME_IMAGE.title_id,)


def test_start_rejected(client: E2aClient) -> None:
    """Un destino desconocido da 400 ``dest_unavailable``."""
    request = Lz4Request(_source(client, GAME_OK.path), "/mnt/usb9/homebrew", 9, True, False)
    with pytest.raises(E2aHttpError) as rejected:
        client.start(request)
    assert (rejected.value.status, rejected.value.code) == (400, "dest_unavailable")
