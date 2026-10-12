"""Doble en memoria de exfat2ampr para los tests de ``services/lz4_*`` (sin red ni esperas)."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from ffpfsc_converter.domain.lz4 import (
    EngineInfo,
    Lz4Check,
    Lz4Compat,
    Lz4Destination,
    Lz4JobState,
    Lz4Request,
    Lz4Source,
    Lz4Status,
)
from ffpfsc_converter.infrastructure.exfat2ampr import E2aHttpError
from ffpfsc_converter.services.lz4_deps import Lz4Deps
from ffpfsc_converter.services.lz4_remote import Lz4Remote
from ffpfsc_converter.services.lz4_settings import Lz4Settings

HOST = "192.168.1.50"
TOKEN = "a" * 32
GAME = Lz4Source("/data/homebrew/PPSA01234", "folder", "PPSA01234", "Juego", "01.000")
IMAGE = Lz4Source("/mnt/usb0/homebrew/X.exfat", "image", "PPSA05678", "Otro", "01.000",
                  "PPSA05678")
INTERNAL = Lz4Destination("/data/homebrew", "internal", -1, "Internal storage", 1000, 500, True)
USB = Lz4Destination("/mnt/usb0/homebrew", "usb", 0, "USB 0", 2000, 1500, True)
OK_CHECK = Lz4Check("PPSA01234", "Juego", 100, 60, 100, 500, 1000, Lz4Compat.YES)


def status(state: Lz4JobState, percent: int = 0, title_id: str = "PPSA01234",
           dest: str = "/data/homebrew/PPSA01234") -> Lz4Status:
    """Crea un estado de ``/api/state`` del juego de prueba."""
    return Lz4Status(state, percent=percent, title_id=title_id, dest=dest)


@dataclass
class FakeClock:
    """Reloj falso: ``sleep`` solo adelanta el tiempo."""

    now: float = 0.0
    sleeps: list[float] = field(default_factory=list)

    def sleep(self, seconds: float) -> None:
        """Adelanta el reloj sin esperar."""
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        """Devuelve la hora falsa."""
        return self.now


@dataclass
class FakeEngine:
    """Estado compartido del motor falso que ven todos sus clientes."""

    is_up: bool = True
    boot_polls: int = 0
    pin: str = "123456"
    tokens: set[str] = field(default_factory=lambda: {TOKEN})
    pair_status: int = 0
    sources: list[Lz4Source] = field(default_factory=lambda: [GAME, IMAGE])
    destinations: list[Lz4Destination] = field(default_factory=lambda: [INTERNAL, USB])
    check_result: Lz4Check = OK_CHECK
    states: list[Lz4Status | Exception] = field(default_factory=list)
    start_error: E2aHttpError | None = None
    sources_error: OSError | None = None
    is_loader_down: bool = False
    state_gate: threading.Event | None = None
    calls: list[str] = field(default_factory=list)
    elf_sent: list[Path] = field(default_factory=list)

    def factory(self, host: str, token: str | None) -> FakeClient:
        """Crea un cliente como ``E2aClient(host, token)``."""
        return FakeClient(self, token)

    def send_elf(self, host: str, elf: Path) -> None:
        """Simula el cargador de ELF: el motor arranca tras ``boot_polls`` sondeos."""
        if self.is_loader_down:
            raise ConnectionRefusedError("cargador de ELF cerrado")
        self.elf_sent.append(elf)
        self.is_up = True

    def next_state(self) -> Lz4Status:
        """Devuelve el siguiente estado programado (el último se repite)."""
        item = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    """Cliente en memoria que cumple el ``Protocol`` ``Lz4Client``."""

    def __init__(self, engine: FakeEngine, token: str | None) -> None:
        """Guarda el motor y el token."""
        self._engine = engine
        self._token = token

    def _call(self, name: str, needs_auth: bool = True) -> None:
        """Registra la llamada y simula red caída o token inválido."""
        self._engine.calls.append(name)
        if not self._engine.is_up:
            raise ConnectionRefusedError("motor apagado")
        if needs_auth and self._token not in self._engine.tokens:
            raise E2aHttpError(401, "pair", "pair")

    def hello(self) -> EngineInfo:
        """Responde ``/api/hello`` (falla mientras el motor arranca)."""
        if self._engine.boot_polls > 0 and self._engine.is_up:
            self._engine.boot_polls -= 1
            self._engine.calls.append("hello")
            raise ConnectionRefusedError("arrancando")
        self._call("hello", needs_auth=False)
        return EngineInfo("1.45", self._token in self._engine.tokens)

    def pair(self, pin: str) -> str:
        """Responde ``/api/pair``."""
        self._call("pair", needs_auth=False)
        if self._engine.pair_status:
            raise E2aHttpError(self._engine.pair_status, "", "bad code")
        if pin != self._engine.pin:
            raise E2aHttpError(403, "bad code", "bad code")
        self._engine.tokens.add(TOKEN)
        return TOKEN

    def sources(self) -> list[Lz4Source]:
        """Responde ``/api/sources``."""
        self._call("sources")
        if self._engine.sources_error is not None:
            raise self._engine.sources_error
        return list(self._engine.sources)

    def destinations(self) -> list[Lz4Destination]:
        """Responde ``/api/destinations``."""
        self._call("destinations")
        return list(self._engine.destinations)

    def check(self, source: Lz4Source, dest_base: str) -> Lz4Check:
        """Responde ``/api/check``."""
        self._call(f"check {source.path} {dest_base}")
        return self._engine.check_result

    def start(self, request: Lz4Request) -> int:
        """Responde ``/api/start``."""
        self._call("start")
        if self._engine.start_error is not None:
            raise self._engine.start_error
        return 0

    def state(self) -> Lz4Status:
        """Responde ``/api/state`` con el siguiente estado programado."""
        self._call("state")
        if self._engine.state_gate is not None:
            self._engine.state_gate.wait(5)
        return self._engine.next_state()

    def pause(self) -> None:
        """Responde ``/api/pause``."""
        self._call("pause")

    def resume(self, dest: str) -> None:
        """Responde ``/api/resume``."""
        self._call(f"resume {dest}")

    def cancel(self) -> None:
        """Responde ``/api/cancel``."""
        self._call("cancel")


def make_deps(engine: FakeEngine, settings_file: Path, clock: FakeClock) -> Lz4Deps:
    """Crea dependencias falsas: motor en memoria, ajustes temporales y reloj falso."""
    return Lz4Deps(client_factory=engine.factory, elf_sender=engine.send_elf,
                   settings=Lz4Settings(settings_file), sleep=clock.sleep, clock=clock.clock)


@dataclass
class Harness:
    """Servicio bajo prueba con su motor falso, su reloj y los eventos publicados."""

    engine: FakeEngine
    clock: FakeClock
    settings: Lz4Settings
    remote: Lz4Remote
    events: list[object]

    def kinds(self) -> list[type]:
        """Devuelve el tipo de cada evento publicado, en orden."""
        return [type(event) for event in self.events]


def make_harness(tmp_path: Path, engine: FakeEngine | None = None) -> Harness:
    """Crea un ``Lz4Remote`` conectado a un motor falso y a ajustes en ``tmp_path``."""
    engine = engine or FakeEngine()
    clock = FakeClock()
    deps = make_deps(engine, tmp_path / "settings.json", clock)
    deps.settings.save_token(HOST, TOKEN)
    events: list[object] = []
    return Harness(engine, clock, deps.settings, Lz4Remote(events.append, deps), events)
