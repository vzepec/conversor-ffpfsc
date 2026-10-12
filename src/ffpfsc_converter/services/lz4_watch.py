"""Seguimiento del avance de una conversión de exfat2ampr.

exfat2ampr conserva el último resultado (``done``, ``error``…) hasta la
siguiente conversión, así que justo después de ``/api/start`` puede verse
todavía el resultado anterior: solo se da por terminada la conversión seguida
cuando antes se la vio en marcha, o cuando el resultado coincide con ella y ya
pasó un margen prudente.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from ffpfsc_converter.config import (
    E2A_POLL_MAX_FAILURES,
    E2A_POLL_SECONDS,
    E2A_STALE_GRACE_SECONDS,
)
from ffpfsc_converter.domain.lz4 import Lz4JobState, Lz4Request, Lz4Status
from ffpfsc_converter.domain.lz4_events import Lz4Finished, Lz4Progress
from ffpfsc_converter.errors import Lz4EngineError
from ffpfsc_converter.services.lz4_deps import Lz4Client, Lz4Deps, Lz4Sink
from ffpfsc_converter.services.lz4_messages import connection_lost_text
from ffpfsc_converter.services.lz4_plan import normalize_remote

_TERMINAL_STATES = frozenset({
    Lz4JobState.DONE, Lz4JobState.ERROR, Lz4JobState.CANCELLED, Lz4JobState.PAUSED,
})


@dataclass(frozen=True)
class WatchTarget:
    """Conversión que se espera ver en ``/api/state``.

    Attributes:
        title_id (str): Juego esperado; vacío acepta cualquiera.
        dests (tuple[str, ...]): Carpetas aceptadas como ``dest``; vacía acepta cualquiera.
    """

    title_id: str = ""
    dests: tuple[str, ...] = ()

    @classmethod
    def for_request(cls, request: Lz4Request) -> WatchTarget:
        """Crea el objetivo que corresponde a una conversión pedida.

        Args:
            request (Lz4Request): Conversión enviada a ``/api/start``.

        Returns:
            WatchTarget: Objetivo con su Title ID y sus carpetas de salida posibles.
        """
        dests = (normalize_remote(request.output_path), normalize_remote(request.dest_base))
        return cls(request.source.title_id, dests)

    def matches(self, status: Lz4Status) -> bool:
        """Indica si un estado de exfat2ampr corresponde a esta conversión.

        Args:
            status (Lz4Status): Estado leído.

        Returns:
            bool: ``True`` si el juego y la carpeta (cuando se conocen) coinciden.
        """
        if self.title_id and status.title_id != self.title_id:
            return False
        if not self.dests or not status.dest:
            return True
        return normalize_remote(status.dest) in self.dests


class JobFollower:
    """Consulta el estado de exfat2ampr hasta que la conversión seguida termina."""

    def __init__(self, host: str, client: Lz4Client, deps: Lz4Deps, emit: Lz4Sink) -> None:
        """Prepara el seguimiento sin empezarlo.

        Args:
            host (str): Dirección de la PS5.
            client (Lz4Client): Cliente emparejado.
            deps (Lz4Deps): Dependencias (reloj y espera).
            emit (Lz4Sink): Destino de ``Lz4Progress`` y ``Lz4Finished``.
        """
        self._host = host
        self._client = client
        self._deps = deps
        self._emit = emit
        self._stop = threading.Event()
        self._failures = 0

    def stop(self) -> None:
        """Pide dejar de seguir la conversión (sigue en la PS5)."""
        self._stop.set()

    def run(self, target: WatchTarget) -> None:
        """Publica el avance hasta que la conversión termine, falle, se cancele o pause.

        Args:
            target (WatchTarget): Conversión a seguir.

        Raises:
            Lz4EngineError: Si fallan ``E2A_POLL_MAX_FAILURES`` consultas seguidas.
        """
        started = self._deps.clock()
        has_seen_active = False
        while not self._stop.is_set():
            status = self._poll()
            if status is not None and status.is_active:
                has_seen_active = has_seen_active or target.matches(status)
                self._emit(Lz4Progress(self._host, status))
            elif status is not None and self._is_final(status, target, has_seen_active, started):
                self._emit(Lz4Finished(self._host, status))
                return
            self._deps.sleep(E2A_POLL_SECONDS)

    def _poll(self) -> Lz4Status | None:
        """Lee el estado tolerando cortes breves de la red.

        Returns:
            Lz4Status | None: Estado leído, o ``None`` si esta consulta falló.

        Raises:
            Lz4EngineError: Si se acumulan ``E2A_POLL_MAX_FAILURES`` fallos seguidos.
        """
        try:
            status = self._client.state()
        except OSError as exc:
            self._failures += 1
            if self._failures >= E2A_POLL_MAX_FAILURES:
                raise Lz4EngineError(connection_lost_text(self._host)) from exc
            return None
        self._failures = 0
        return status

    def _is_final(self, status: Lz4Status, target: WatchTarget, has_seen_active: bool,
                  started: float) -> bool:
        """Decide si un estado inactivo es el resultado de la conversión seguida.

        Args:
            status (Lz4Status): Estado inactivo leído.
            target (WatchTarget): Conversión seguida.
            has_seen_active (bool): ``True`` si ya se la vio en marcha.
            started (float): Momento (reloj de ``deps``) en que empezó el seguimiento.

        Returns:
            bool: ``True`` si hay que publicar ``Lz4Finished``.
        """
        if has_seen_active:
            return True
        if status.state not in _TERMINAL_STATES or not target.matches(status):
            return False
        return self._deps.clock() - started >= E2A_STALE_GRACE_SECONDS
