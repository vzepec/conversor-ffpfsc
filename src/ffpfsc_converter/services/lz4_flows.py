"""Pasos de cada orden de la compresión LZ4 remota, ejecutados en el hilo que los llama.

:class:`~ffpfsc_converter.services.lz4_remote.Lz4Remote` los lanza en hilos
daemon y convierte sus errores en eventos.
"""
from __future__ import annotations

from http import HTTPStatus

from ffpfsc_converter.domain.lz4 import EngineInfo, Lz4Request
from ffpfsc_converter.domain.lz4_events import (
    Lz4ElfRequired,
    Lz4Failed,
    Lz4PairingRequired,
    Lz4Ready,
    Lz4Rejected,
    Lz4Started,
)
from ffpfsc_converter.infrastructure.exfat2ampr import E2aHttpError
from ffpfsc_converter.services.lz4_deps import Lz4Client, Lz4Deps, Lz4Sink
from ffpfsc_converter.services.lz4_engine import build_plan, launch_engine, reach_engine
from ffpfsc_converter.services.lz4_messages import PAIR_BLOCKED_TEXT
from ffpfsc_converter.services.lz4_plan import normalize_remote
from ffpfsc_converter.services.lz4_tracking import FollowerRegistry
from ffpfsc_converter.services.lz4_watch import WatchTarget, is_ongoing


class Lz4Flows:
    """Prepara, empareja, inicia, reanuda y sigue conversiones (de forma síncrona)."""

    def __init__(self, deps: Lz4Deps, emit: Lz4Sink, followers: FollowerRegistry) -> None:
        """Guarda las dependencias compartidas con el servicio.

        Args:
            deps (Lz4Deps): Dependencias (cliente, ajustes, reloj).
            emit (Lz4Sink): Destino de los eventos.
            followers (FollowerRegistry): Seguimientos activos.
        """
        self._deps = deps
        self._emit = emit
        self._followers = followers

    def prepare(self, host: str, entry_path: str) -> None:
        """Arranca el motor si hace falta y continúa con el emparejamiento y el análisis.

        Args:
            host (str): Dirección de la PS5.
            entry_path (str): Juego elegido.
        """
        client = self._deps.client(host)
        info = reach_engine(client)
        if info is None:
            elf = self._deps.settings.elf_path()
            if elf is None:
                self._emit(Lz4ElfRequired(host, entry_path))
                return
            info = launch_engine(host, elf, self._deps, self._emit)
        self._analyze(host, client, info, entry_path)

    def pair(self, host: str, pin: str, entry_path: str) -> None:
        """Pide el token con el código, lo guarda y sigue con el análisis.

        Args:
            host (str): Dirección de la PS5.
            pin (str): Código de emparejamiento.
            entry_path (str): Juego elegido.

        Raises:
            E2aHttpError: Si exfat2ampr responde con un error distinto de 403 o 429.
        """
        try:
            token = self._deps.client_factory(host, None).pair(pin)
        except E2aHttpError as exc:
            if exc.status == HTTPStatus.FORBIDDEN:
                self._emit(Lz4PairingRequired(host, entry_path, retry=True))
                return
            if exc.status == HTTPStatus.TOO_MANY_REQUESTS:
                self._emit(Lz4Failed(host, PAIR_BLOCKED_TEXT))
                return
            raise
        self._deps.settings.save_token(host, token)
        client = self._deps.client(host)
        self._analyze(host, client, client.hello(), entry_path)

    def _analyze(self, host: str, client: Lz4Client, info: EngineInfo, entry_path: str) -> None:
        """Pide emparejar si hace falta o publica el plan del juego.

        Args:
            host (str): Dirección de la PS5.
            client (Lz4Client): Cliente con el token guardado.
            info (EngineInfo): Respuesta de ``/api/hello``.
            entry_path (str): Juego elegido.
        """
        if not info.paired:
            self._deps.settings.forget_token(host)
            self._emit(Lz4PairingRequired(host, entry_path))
            return
        self._emit(Lz4Ready(host, build_plan(client, entry_path)))

    def start(self, host: str, request: Lz4Request) -> None:
        """Hace la comprobación final, pide la conversión y la sigue.

        Args:
            host (str): Dirección de la PS5.
            request (Lz4Request): Conversión a pedir.
        """
        client = self._deps.client(host)
        check = client.check(request.source, request.dest_base)
        if check.is_blocked:
            self._emit(Lz4Rejected(host, check))
            return
        position = client.start(request)
        self._emit(Lz4Started(host, request, position))
        self._followers.follow(host, client, WatchTarget.for_request(request))

    def resume(self, host: str, dest: str) -> None:
        """Reanuda la conversión en pausa y la sigue hasta el final.

        Args:
            host (str): Dirección de la PS5.
            dest (str): Carpeta de salida de la conversión.
        """
        client = self._deps.client(host)
        client.resume(dest)
        self._followers.follow(host, client, WatchTarget(dests=(normalize_remote(dest),)))

    def watch(self, host: str) -> None:
        """Sigue la conversión activa, si la hay, sin publicar errores de conexión.

        Args:
            host (str): Dirección de la PS5.
        """
        if self._followers.busy or self._deps.settings.token(host) is None:
            return
        client = self._deps.client(host)
        try:
            status = client.state()
        except (OSError, E2aHttpError):
            return
        if is_ongoing(status):
            self._followers.follow(host, client, WatchTarget(status.title_id))
