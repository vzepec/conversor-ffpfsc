"""Comportamiento del exfat2ampr falso: autenticación, emparejamiento y consultas.

Sin red: :class:`FakeE2aLogic` recibe una :class:`FakeRequest` ya interpretada y
devuelve una :class:`FakeReply`. Las rutas de conversión están en
:mod:`e2a_fake_job_routes` y el servidor HTTP en :mod:`e2a_fake`.
"""
from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Iterable

from e2a_fake_data import (
    DEST_INTERNAL,
    DEST_USB,
    GAME_IMAGE,
    GAME_NOT_AMPR,
    GAME_OK,
    FakeConsoleData,
    FakeDestination,
    FakeGame,
    FakeReply,
    FakeRequest,
    check_json,
    destination_json,
    error_reply,
    output_path,
    source_json,
)
from e2a_fake_job_routes import JobRoutes, Route
from e2a_fake_jobs import FakeJob, JobBoard

OPEN_PATHS = frozenset({"/", "/index.html", "/api/hello", "/api/pair"})
MAX_PIN_FAILURES = 5


class FakeE2aLogic:
    """Comportamiento de exfat2ampr 1.45 sin la parte HTTP (seguro entre hilos).

    Attributes:
        pin (str): Código de emparejamiento vigente.
        next_pin (str): Código que pasa a valer tras 5 fallos.
        block_seconds (float): Duración del bloqueo tras 5 fallos.
        tokens (set[str]): Tokens válidos.
        requests (list[FakeRequest]): Peticiones recibidas, en orden.
        console (FakeConsoleData): Juegos, unidades y salidas existentes.
        jobs (JobBoard): Conversiones (``jobs.auto_step``, ``jobs.stale_polls``).
    """

    def __init__(self, pin: str = "123456", games: Iterable[FakeGame] | None = None,
                 destinations: Iterable[FakeDestination] | None = None) -> None:
        """Crea el motor con el PIN y los juegos indicados (por defecto, tres de ejemplo).

        Args:
            pin (str): Código de emparejamiento que mostraría la PS5.
            games (Iterable[FakeGame] | None): Juegos; por defecto compatible, sin AMPR e imagen.
            destinations (Iterable[FakeDestination] | None): Unidades; por defecto interna y USB.
        """
        self.pin = pin
        self.next_pin = "654321"
        self.block_seconds = 60.0
        self.tokens: set[str] = set()
        self.requests: list[FakeRequest] = []
        self.console = FakeConsoleData(
            {g.path: g for g in (games or (GAME_OK, GAME_NOT_AMPR, GAME_IMAGE))},
            list(destinations or (DEST_INTERNAL, DEST_USB)),
        )
        self.jobs = JobBoard(self.console)
        self.lock = threading.RLock()
        self._failures = 0
        self._blocked_until = 0.0
        self._routes: dict[str, Route] = {
            "/api/hello": self._hello, "/api/pair": self._pair,
            "/api/sources": self._sources, "/api/destinations": self._destinations,
            "/api/check": self._check, **JobRoutes(self.console, self.jobs).routes(),
        }

    def handle(self, request: FakeRequest) -> FakeReply:
        """Registra una petición y la responde como el motor real.

        Returns:
            FakeReply: Respuesta (401 ``pair`` sin token válido en rutas protegidas).
        """
        with self.lock:
            self.requests.append(request)
            if request.path in ("/", "/index.html"):
                return FakeReply(200, {"page": "exfat2ampr"})
            route = self._routes.get(request.path)
            if route is None:
                return error_reply(404, "not found")
            if request.path not in OPEN_PATHS and request.token not in self.tokens:
                return error_reply(401, "pair")
            return route(request)

    def issue_token(self) -> str:
        """Empareja directamente (como si el usuario ya hubiera puesto el código).

        Returns:
            str: Token válido.
        """
        with self.lock:
            token = secrets.token_hex(16)
            self.tokens.add(token)
            return token

    def advance(self, percent: int) -> None:
        """Avanza la conversión actual (la arranca si aún mostraba el resultado anterior)."""
        with self.lock:
            self.jobs.advance(percent)

    def finish(self, state: str = "done", code: str = "") -> None:
        """Termina la conversión actual (``done``, ``error``, ``cancelled`` o ``paused``)."""
        with self.lock:
            self.jobs.finish(state, code)

    def seed_result(self, game: FakeGame, state: str = "done", code: str = "") -> None:
        """Deja un resultado anterior visible en ``/api/state`` (como tras otra conversión)."""
        with self.lock:
            dest = output_path(DEST_INTERNAL.base, game.title_id)
            self.jobs.result = FakeJob(game, dest, state=state, percent=100, code=code)

    def paths(self) -> list[str]:
        """Lista las rutas pedidas, en orden.

        Returns:
            list[str]: Una ruta por petición recibida.
        """
        with self.lock:
            return [request.path for request in self.requests]

    def last(self, path: str) -> FakeRequest:
        """Devuelve la última petición a una ruta.

        Returns:
            FakeRequest: La petición.
        """
        with self.lock:
            return next(r for r in reversed(self.requests) if r.path == path)

    def _hello(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/hello``.

        Returns:
            FakeReply: Versión y si el token es válido.
        """
        return FakeReply(200, {"paired": request.token in self.tokens, "local": False,
                               "version": "1.45"})

    def _pair(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/pair``: token, 403 con código malo o 429 tras 5 fallos.

        Returns:
            FakeReply: Resultado del emparejamiento.
        """
        if time.monotonic() < self._blocked_until:
            return error_reply(429, "blocked")
        if request.params.get("pin") == self.pin:
            self._failures = 0
            return FakeReply(200, {"token": self.issue_token()})
        self._failures += 1
        if self._failures < MAX_PIN_FAILURES:
            return error_reply(403, "bad code")
        self._failures, self.pin = 0, self.next_pin
        self._blocked_until = time.monotonic() + self.block_seconds
        return error_reply(429, "blocked")

    def _sources(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/sources``.

        Returns:
            FakeReply: Lista de juegos.
        """
        return FakeReply(200, [source_json(g) for g in self.console.games.values()])

    def _destinations(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/destinations``.

        Returns:
            FakeReply: Lista de unidades.
        """
        return FakeReply(200, [destination_json(d) for d in self.console.destinations])

    def _check(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/check``.

        Returns:
            FakeReply: Comprobación previa.
        """
        return FakeReply(200, check_json(self.console, request.params))
