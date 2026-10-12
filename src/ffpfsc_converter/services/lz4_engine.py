"""Arranque de exfat2ampr y análisis del juego elegido.

Si el motor no responde, se le envía el ``exfat2ampr.elf`` que eligió el
usuario al cargador de ELF de la PS5 y se espera a que conteste.
"""
from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.config import E2A_START_POLL_SECONDS, E2A_START_TIMEOUT_SECONDS
from ffpfsc_converter.domain.lz4 import EngineInfo, Lz4Plan
from ffpfsc_converter.domain.lz4_events import Lz4EngineLaunched
from ffpfsc_converter.errors import Lz4EngineError, Lz4EngineUnavailableError
from ffpfsc_converter.services.lz4_deps import Lz4Client, Lz4Deps, Lz4Sink
from ffpfsc_converter.services.lz4_messages import (
    ELF_SEND_ERROR_TEXT,
    LAUNCH_TIMEOUT_TEXT,
    NO_DESTINATION_TEXT,
    SOURCE_MISSING_TEXT,
)
from ffpfsc_converter.services.lz4_plan import find_source, suggest_destination


def reach_engine(client: Lz4Client) -> EngineInfo | None:
    """Pregunta a exfat2ampr si está en marcha.

    Args:
        client (Lz4Client): Cliente de la consola.

    Returns:
        EngineInfo | None: Respuesta del motor, o ``None`` si no responde.
    """
    try:
        return client.hello()
    except OSError:
        return None


def launch_engine(host: str, elf: Path, deps: Lz4Deps, emit: Lz4Sink) -> EngineInfo:
    """Envía exfat2ampr al cargador de ELF y espera a que responda.

    Args:
        host (str): Dirección de la PS5.
        elf (Path): ``exfat2ampr.elf`` local.
        deps (Lz4Deps): Dependencias (envío, reloj, espera).
        emit (Lz4Sink): Destino de ``Lz4EngineLaunched``.

    Returns:
        EngineInfo: Primera respuesta del motor ya en marcha.

    Raises:
        Lz4EngineUnavailableError: Si no se pudo enviar el ELF o el motor no arrancó a tiempo.
    """
    try:
        deps.elf_sender(host, elf)
    except OSError as exc:
        raise Lz4EngineUnavailableError(ELF_SEND_ERROR_TEXT) from exc
    emit(Lz4EngineLaunched(host))
    return _wait_for_engine(host, deps)


def _wait_for_engine(host: str, deps: Lz4Deps) -> EngineInfo:
    """Sondea ``/api/hello`` hasta que el motor responda o se agote el plazo.

    Args:
        host (str): Dirección de la PS5.
        deps (Lz4Deps): Dependencias (cliente, reloj, espera).

    Returns:
        EngineInfo: Respuesta del motor.

    Raises:
        Lz4EngineUnavailableError: Si no responde en ``E2A_START_TIMEOUT_SECONDS``.
    """
    client = deps.client(host)
    deadline = deps.clock() + E2A_START_TIMEOUT_SECONDS
    while True:
        deps.sleep(E2A_START_POLL_SECONDS)
        info = reach_engine(client)
        if info is not None:
            return info
        if deps.clock() >= deadline:
            raise Lz4EngineUnavailableError(LAUNCH_TIMEOUT_TEXT)


def build_plan(client: Lz4Client, entry_path: str) -> Lz4Plan:
    """Identifica el juego, sugiere un destino y hace la comprobación previa.

    Args:
        client (Lz4Client): Cliente emparejado.
        entry_path (str): Carpeta o imagen elegida en la PS5.

    Returns:
        Lz4Plan: Juego, comprobación contra el destino sugerido y unidades.

    Raises:
        Lz4EngineError: Si exfat2ampr no reconoce el juego o ninguna unidad admite escritura.
    """
    source = find_source(client.sources(), entry_path)
    if source is None:
        raise Lz4EngineError(SOURCE_MISSING_TEXT)
    destinations = tuple(client.destinations())
    destination = suggest_destination(destinations, source.path)
    if destination is None:
        raise Lz4EngineError(NO_DESTINATION_TEXT)
    check = client.check(source, destination.base)
    return Lz4Plan(source, check, destinations, destination.base)
