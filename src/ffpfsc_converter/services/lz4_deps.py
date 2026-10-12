"""Contrato del cliente de exfat2ampr y dependencias inyectables de la compresión LZ4.

Todo lo que habla con la red, duerme o mide el tiempo se agrupa en
:class:`Lz4Deps` para poder sustituirlo en los tests.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ffpfsc_converter.domain.lz4 import (
    EngineInfo,
    Lz4Check,
    Lz4Destination,
    Lz4Request,
    Lz4Source,
    Lz4Status,
)
from ffpfsc_converter.domain.lz4_events import Lz4Event
from ffpfsc_converter.infrastructure.exfat2ampr import E2aClient, send_elf
from ffpfsc_converter.services.lz4_settings import Lz4Settings


class Lz4Client(Protocol):
    """Operaciones de la API HTTP de exfat2ampr que usa el servicio."""

    def hello(self) -> EngineInfo:
        """Comprueba que el motor responde y si el token es válido.

        Returns:
            EngineInfo: Versión y estado del emparejamiento.
        """
        ...

    def pair(self, pin: str) -> str:
        """Empareja la app con el código que muestra la PS5.

        Args:
            pin (str): Código de 6 dígitos.

        Returns:
            str: Token de emparejamiento.
        """
        ...

    def sources(self) -> list[Lz4Source]:
        """Lista los juegos que exfat2ampr puede convertir.

        Returns:
            list[Lz4Source]: Juegos encontrados.
        """
        ...

    def destinations(self) -> list[Lz4Destination]:
        """Lista las unidades donde puede quedar el juego convertido.

        Returns:
            list[Lz4Destination]: Unidades con su espacio.
        """
        ...

    def check(self, source: Lz4Source, dest_base: str) -> Lz4Check:
        """Hace la comprobación previa de un juego contra un destino.

        Args:
            source (Lz4Source): Juego.
            dest_base (str): Carpeta de juegos del destino.

        Returns:
            Lz4Check: Resultado de la comprobación.
        """
        ...

    def start(self, request: Lz4Request) -> int:
        """Pide la conversión.

        Args:
            request (Lz4Request): Conversión a iniciar.

        Returns:
            int: Lugar en la cola (``0`` = empieza ya).
        """
        ...

    def state(self) -> Lz4Status:
        """Lee el estado de la conversión.

        Returns:
            Lz4Status: Estado actual.
        """
        ...

    def pause(self) -> None:
        """Pausa la conversión dejando un punto de reanudación."""
        ...

    def resume(self, dest: str) -> None:
        """Reanuda una conversión en pausa.

        Args:
            dest (str): Carpeta de salida de la conversión.
        """
        ...

    def cancel(self) -> None:
        """Cancela la conversión y borra su salida parcial."""
        ...


#: Crea un cliente de exfat2ampr a partir de la dirección y el token (o ``None``).
ClientFactory = Callable[[str, str | None], Lz4Client]
#: Recibe los eventos de la compresión LZ4; debe poder llamarse desde cualquier hilo.
Lz4Sink = Callable[[Lz4Event], None]
#: Envía un ELF al cargador de la PS5 (dirección, archivo); lanza ``OSError`` si falla.
ElfSender = Callable[[str, Path], None]


@dataclass(frozen=True)
class Lz4Deps:
    """Dependencias de :class:`~ffpfsc_converter.services.lz4_remote.Lz4Remote`.

    Attributes:
        client_factory (ClientFactory): Crea el cliente HTTP de exfat2ampr.
        elf_sender (ElfSender): Envía ``exfat2ampr.elf`` al cargador de ELF.
        settings (Lz4Settings): Tokens de emparejamiento y ruta del ELF.
        sleep (Callable[[float], None]): Espera los segundos indicados.
        clock (Callable[[], float]): Reloj monotónico en segundos.
    """

    client_factory: ClientFactory = E2aClient
    elf_sender: ElfSender = send_elf
    settings: Lz4Settings = field(default_factory=Lz4Settings)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic

    def client(self, host: str) -> Lz4Client:
        """Crea un cliente con el token guardado para la consola.

        Args:
            host (str): Dirección de la PS5.

        Returns:
            Lz4Client: Cliente listo para usar.
        """
        return self.client_factory(host, self.settings.token(host))
