from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.config import E2A_START_TIMEOUT_SECONDS
from ffpfsc_converter.domain.lz4_events import (
    Lz4ElfRequired,
    Lz4EngineLaunched,
    Lz4Failed,
    Lz4PairingRequired,
    Lz4Ready,
)
from ffpfsc_converter.services.lz4_messages import LAUNCH_TIMEOUT_TEXT, NETWORK_ERROR_TEXT
from lz4_fake_client import GAME, HOST, IMAGE, INTERNAL, TOKEN, USB, FakeEngine, make_harness

_JOIN = 5


def _elf(tmp_path: Path) -> Path:
    """Crea un ``exfat2ampr.elf`` falso."""
    elf = tmp_path / "exfat2ampr.elf"
    elf.write_bytes(b"\x7fELF")
    return elf


def test_engine_down_without_elf_asks_for_it(tmp_path: Path) -> None:
    """Si el motor no responde y no hay ELF elegido, publica ``Lz4ElfRequired``."""
    harness = make_harness(tmp_path, FakeEngine(is_up=False))
    harness.remote.prepare(HOST, GAME.path).join(_JOIN)
    assert harness.events == [Lz4ElfRequired(HOST, GAME.path)]


def test_engine_down_with_elf_is_launched(tmp_path: Path) -> None:
    """Con ELF elegido lo envía, avisa, espera a que responda y publica el plan."""
    harness = make_harness(tmp_path, FakeEngine(is_up=False, boot_polls=3))
    harness.settings.save_elf_path(_elf(tmp_path))
    harness.remote.prepare(HOST, GAME.path).join(_JOIN)
    assert harness.engine.elf_sent == [_elf(tmp_path)]
    assert harness.kinds() == [Lz4EngineLaunched, Lz4Ready]
    assert len(harness.clock.sleeps) == 4


def test_engine_that_never_starts_fails(tmp_path: Path) -> None:
    """Si tras enviar el ELF el motor no responde a tiempo, publica ``Lz4Failed``."""
    harness = make_harness(tmp_path, FakeEngine(is_up=False, boot_polls=10_000))
    harness.settings.save_elf_path(_elf(tmp_path))
    harness.remote.prepare(HOST, GAME.path).join(_JOIN)
    assert harness.kinds() == [Lz4EngineLaunched, Lz4Failed]
    assert harness.events[-1].message == LAUNCH_TIMEOUT_TEXT  # type: ignore[attr-defined]
    assert harness.clock.now >= E2A_START_TIMEOUT_SECONDS


def test_elf_send_failure_is_reported(tmp_path: Path) -> None:
    """Si el cargador de ELF no acepta la conexión, lo explica sin esperar."""
    harness = make_harness(tmp_path, FakeEngine(is_up=False, is_loader_down=True))
    harness.settings.save_elf_path(_elf(tmp_path))
    harness.remote.prepare(HOST, GAME.path).join(_JOIN)
    assert harness.kinds() == [Lz4Failed]
    assert "etaHEN" in harness.events[0].message  # type: ignore[attr-defined]
    assert harness.clock.sleeps == []


def test_unpaired_app_asks_for_code(tmp_path: Path) -> None:
    """Sin token válido pide el código de emparejamiento y olvida el token viejo."""
    harness = make_harness(tmp_path, FakeEngine(tokens=set()))
    harness.remote.prepare(HOST, GAME.path).join(_JOIN)
    assert harness.events == [Lz4PairingRequired(HOST, GAME.path)]
    assert harness.settings.token(HOST) is None


def test_good_pin_saves_token_and_continues(tmp_path: Path) -> None:
    """Un código correcto guarda el token y llega al plan del juego."""
    harness = make_harness(tmp_path, FakeEngine(tokens=set()))
    harness.settings.forget_token(HOST)
    harness.remote.pair(HOST, "123456", GAME.path).join(_JOIN)
    assert harness.settings.token(HOST) == TOKEN
    assert harness.kinds() == [Lz4Ready]


def test_bad_pin_asks_again(tmp_path: Path) -> None:
    """Un código incorrecto vuelve a pedirlo marcando ``retry``."""
    harness = make_harness(tmp_path, FakeEngine(tokens=set()))
    harness.remote.pair(HOST, "000000", GAME.path).join(_JOIN)
    assert harness.events == [Lz4PairingRequired(HOST, GAME.path, retry=True)]


def test_blocked_pairing_fails_with_advice(tmp_path: Path) -> None:
    """Tras demasiados intentos (429) explica que hay que esperar y recargar el motor."""
    harness = make_harness(tmp_path, FakeEngine(tokens=set(), pair_status=429))
    harness.remote.pair(HOST, "123456", GAME.path).join(_JOIN)
    assert harness.kinds() == [Lz4Failed]
    assert "Espera un minuto" in harness.events[0].message  # type: ignore[attr-defined]


def test_unknown_game_fails(tmp_path: Path) -> None:
    """Si exfat2ampr no reconoce la ruta como juego, publica ``Lz4Failed``."""
    harness = make_harness(tmp_path)
    harness.remote.prepare(HOST, "/data/homebrew/no-es-juego").join(_JOIN)
    assert harness.kinds() == [Lz4Failed]
    assert "No se puede comprimir" in harness.events[0].message  # type: ignore[attr-defined]


def test_ready_plan_suggests_same_drive(tmp_path: Path) -> None:
    """El plan comprueba el juego contra la misma unidad e incluye todas las unidades."""
    harness = make_harness(tmp_path)
    harness.remote.prepare(HOST, IMAGE.path + "/").join(_JOIN)
    ready = harness.events[0]
    assert isinstance(ready, Lz4Ready)
    assert ready.plan.source == IMAGE
    assert ready.plan.dest_base == USB.base
    assert ready.plan.destinations == (INTERNAL, USB)
    assert f"check {IMAGE.path} {USB.base}" in harness.engine.calls


def test_no_writable_drive_fails(tmp_path: Path) -> None:
    """Si ninguna unidad admite escritura, no publica un plan."""
    harness = make_harness(tmp_path, FakeEngine(destinations=[]))
    harness.remote.prepare(HOST, GAME.path).join(_JOIN)
    assert harness.kinds() == [Lz4Failed]


def test_network_error_after_hello_fails(tmp_path: Path) -> None:
    """Un corte de red a mitad del análisis se publica como ``Lz4Failed``."""
    harness = make_harness(tmp_path, FakeEngine(sources_error=TimeoutError()))
    harness.remote.prepare(HOST, GAME.path).join(_JOIN)
    assert harness.kinds() == [Lz4Failed]
    assert harness.events[0].message == NETWORK_ERROR_TEXT  # type: ignore[attr-defined]
