"""Arnés de punta a punta de la compresión LZ4: servicio real, cliente HTTP real y motor falso.

Une :class:`~ffpfsc_converter.services.lz4_remote.Lz4Remote`, ``E2aClient`` y
``send_elf`` reales con :class:`e2a_fake.FakeE2aEngine` y
:class:`e2a_fake.FakeElfLoader` en ``127.0.0.1``. Las esperas del servicio se
aceleran con un reloj escalado (inyectado en ``Lz4Deps``), así que los plazos de
``config.py`` (sondeo, margen, arranque) duran centésimas de segundo.
"""
from __future__ import annotations

import queue
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from e2a_fake import FakeE2aEngine, FakeElfLoader
from ffpfsc_converter.domain.lz4 import Lz4Plan, Lz4Request, Lz4Status
from ffpfsc_converter.domain.lz4_events import Lz4Progress
from ffpfsc_converter.infrastructure.exfat2ampr import E2aClient, send_elf
from ffpfsc_converter.services.lz4_deps import Lz4Client, Lz4Deps
from ffpfsc_converter.services.lz4_plan import output_name
from ffpfsc_converter.services.lz4_remote import Lz4Remote
from ffpfsc_converter.services.lz4_settings import Lz4Settings

#: Fracción real de cada segundo de espera del servicio (1 s del servicio = 10 ms).
TIME_SCALE = 0.01
EVENT_TIMEOUT = 5.0
NET_TIMEOUT = 2.0
ELF_BYTES = b"\x7fELF exfat2ampr falso"

EventT = TypeVar("EventT")


def scaled_sleep(seconds: float) -> None:
    """Espera una fracción ``TIME_SCALE`` de los segundos pedidos."""
    time.sleep(seconds * TIME_SCALE)


def scaled_clock() -> float:
    """Devuelve un reloj monotónico que avanza ``1 / TIME_SCALE`` veces más rápido."""
    return time.monotonic() / TIME_SCALE


@dataclass
class E2eFlow:
    """Servicio real conectado al motor y al cargador falsos, con sus eventos en una cola."""

    engine: FakeE2aEngine
    loader: FakeElfLoader
    settings: Lz4Settings
    remote: Lz4Remote
    events: queue.Queue[object]

    @property
    def host(self) -> str:
        """Devuelve la dirección de la «PS5» falsa."""
        return self.engine.host

    def expect(self, kind: type[EventT]) -> EventT:
        """Espera el siguiente evento distinto de ``Lz4Progress`` (salvo que se pida ese)."""
        deadline = time.monotonic() + EVENT_TIMEOUT
        while True:
            event = self.events.get(timeout=max(deadline - time.monotonic(), 0.01))
            if isinstance(event, Lz4Progress) and kind is not Lz4Progress:
                continue
            assert isinstance(event, kind), f"se esperaba {kind.__name__} y llegó {event!r}"
            return event

    def expect_progress(self, check: Callable[[Lz4Status], bool]) -> Lz4Progress:
        """Espera un ``Lz4Progress`` que cumpla ``check`` (falla si antes llega otro evento)."""
        while True:
            event = self.expect(Lz4Progress)
            if check(event.status):
                return event

    def stop(self) -> None:
        """Deja de seguir conversiones y apaga el motor y el cargador falsos."""
        self.remote.stop_watching()
        self.engine.stop()
        self.loader.stop()


def request_for(plan: Lz4Plan) -> Lz4Request:
    """Arma la conversión que confirmaría el usuario con las opciones por defecto."""
    return Lz4Request(plan.source, plan.dest_base, level=9, verify=True, remove_source=False,
                      name=output_name(plan.source, plan.dest_base))


def make_flow(tmp_path: Path, is_engine_up: bool = False, is_paired: bool = False) -> E2eFlow:
    """Crea el servicio real contra un motor falso y un cargador que lo arranca al recibir el ELF.

    Args:
        tmp_path (Path): Carpeta temporal del test (ajustes y ELF).
        is_engine_up (bool): ``True`` para que el motor ya responda.
        is_paired (bool): ``True`` para guardar de antemano un token válido.
    """
    engine = FakeE2aEngine()
    loader = FakeElfLoader(on_receive=lambda _elf: engine.start())
    settings = Lz4Settings(tmp_path / "settings.json", tmp_path / "third_party")
    elf = tmp_path / "exfat2ampr.elf"
    elf.write_bytes(ELF_BYTES)
    settings.save_elf_path(elf)
    if is_engine_up:
        engine.start()
    if is_paired:
        settings.save_token(engine.host, engine.issue_token())

    def client_factory(host: str, token: str | None) -> Lz4Client:
        """Crea un ``E2aClient`` real que apunta al puerto del motor falso."""
        return E2aClient(host, token, port=engine.port, timeout=NET_TIMEOUT)

    def elf_sender(host: str, path: Path) -> None:
        """Envía el ELF con ``send_elf`` real al cargador falso."""
        send_elf(host, path, port=loader.port, timeout=NET_TIMEOUT)

    deps = Lz4Deps(client_factory, elf_sender, settings, scaled_sleep, scaled_clock)
    events: queue.Queue[object] = queue.Queue()
    return E2eFlow(engine, loader, settings, Lz4Remote(events.put, deps), events)


@contextmanager
def running_flow(tmp_path: Path, is_engine_up: bool = False,
                 is_paired: bool = False) -> Iterator[E2eFlow]:
    """Crea el arnés con :func:`make_flow` y lo apaga al salir del bloque."""
    flow = make_flow(tmp_path, is_engine_up, is_paired)
    try:
        yield flow
    finally:
        flow.stop()
