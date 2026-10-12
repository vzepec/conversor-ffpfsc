"""Eventos de la compresión LZ4 remota (exfat2ampr).

Los publica :class:`~ffpfsc_converter.services.lz4_remote.Lz4Remote` desde hilos
de fondo; la vista PS5 los consume en el hilo de la interfaz.
"""
from __future__ import annotations

from dataclasses import dataclass

from ffpfsc_converter.domain.lz4 import Lz4Check, Lz4Plan, Lz4Request, Lz4Status


@dataclass(frozen=True)
class Lz4EngineLaunched:
    """Se envió exfat2ampr al cargador de ELF; la PS5 muestra su código en una notificación.

    Attributes:
        host (str): Dirección de la PS5.
    """

    host: str


@dataclass(frozen=True)
class Lz4ElfRequired:
    """exfat2ampr no responde y no hay un ``exfat2ampr.elf`` elegido para enviarlo.

    Attributes:
        host (str): Dirección de la PS5.
        entry_path (str): Juego que se quería convertir (para continuar tras elegir el ELF).
    """

    host: str
    entry_path: str


@dataclass(frozen=True)
class Lz4PairingRequired:
    """exfat2ampr responde pero esta app no está emparejada: hay que pedir el código.

    Attributes:
        host (str): Dirección de la PS5.
        entry_path (str): Juego que se quería convertir (para continuar tras emparejar).
        retry (bool): ``True`` si el código anterior fue incorrecto.
    """

    host: str
    entry_path: str
    retry: bool = False


@dataclass(frozen=True)
class Lz4Ready:
    """Juego analizado: se puede mostrar la ventana de compresión.

    Attributes:
        host (str): Dirección de la PS5.
        plan (Lz4Plan): Juego, comprobación previa y destinos.
    """

    host: str
    plan: Lz4Plan


@dataclass(frozen=True)
class Lz4Rejected:
    """La comprobación final contra el destino elegido encontró errores; no se inició.

    Attributes:
        host (str): Dirección de la PS5.
        check (Lz4Check): Comprobación con los códigos de error.
    """

    host: str
    check: Lz4Check


@dataclass(frozen=True)
class Lz4Started:
    """exfat2ampr aceptó la conversión.

    Attributes:
        host (str): Dirección de la PS5.
        request (Lz4Request): Conversión pedida.
        position (int): Lugar en la cola de exfat2ampr (``0`` = empieza ya).
    """

    host: str
    request: Lz4Request
    position: int


@dataclass(frozen=True)
class Lz4Progress:
    """Avance de la conversión (se publica como máximo cada ``E2A_POLL_SECONDS``).

    Attributes:
        host (str): Dirección de la PS5.
        status (Lz4Status): Estado leído de exfat2ampr.
    """

    host: str
    status: Lz4Status


@dataclass(frozen=True)
class Lz4Finished:
    """La conversión terminó, falló, se canceló o quedó en pausa.

    Attributes:
        host (str): Dirección de la PS5.
        status (Lz4Status): Último estado (``state`` indica el resultado).
    """

    host: str
    status: Lz4Status


@dataclass(frozen=True)
class Lz4Failed:
    """No se pudo hablar con exfat2ampr o este rechazó la orden.

    Attributes:
        host (str): Dirección de la PS5.
        message (str): Motivo listo para mostrar (español neutro).
    """

    host: str
    message: str


Lz4Event = (
    Lz4EngineLaunched
    | Lz4ElfRequired
    | Lz4PairingRequired
    | Lz4Ready
    | Lz4Rejected
    | Lz4Started
    | Lz4Progress
    | Lz4Finished
    | Lz4Failed
)
