"""Registro de las conversiones LZ4 que se están iniciando o siguiendo.

Permite saber si el servicio está ocupado y detener todos los seguimientos
(las conversiones continúan en la PS5).
"""
from __future__ import annotations

import threading
from collections.abc import Callable

from ffpfsc_converter.services.lz4_deps import Lz4Client, Lz4Deps, Lz4Sink
from ffpfsc_converter.services.lz4_watch import JobFollower, WatchTarget


class FollowerRegistry:
    """Cuenta las órdenes en curso y guarda los seguimientos activos (seguro entre hilos)."""

    def __init__(self, deps: Lz4Deps, emit: Lz4Sink) -> None:
        """Prepara un registro vacío.

        Args:
            deps (Lz4Deps): Dependencias para los seguimientos.
            emit (Lz4Sink): Destino de los eventos de avance.
        """
        self._deps = deps
        self._emit = emit
        self._lock = threading.Lock()
        self._pending = 0
        self._followers: set[JobFollower] = set()

    @property
    def busy(self) -> bool:
        """Indica si hay una conversión iniciándose o en seguimiento.

        Returns:
            bool: ``True`` si hay alguna orden marcada o algún seguimiento activo.
        """
        with self._lock:
            return self._pending > 0 or bool(self._followers)

    def tracked(self, task: Callable[[], None]) -> Callable[[], None]:
        """Marca el servicio como ocupado desde ya hasta que la tarea termine.

        Args:
            task (Callable[[], None]): Tarea que se ejecutará en otro hilo.

        Returns:
            Callable[[], None]: Tarea envuelta que libera la marca al terminar.
        """
        with self._lock:
            self._pending += 1

        def run() -> None:
            """Ejecuta la tarea y libera la marca aunque falle."""
            try:
                task()
            finally:
                with self._lock:
                    self._pending -= 1

        return run

    def follow(self, host: str, client: Lz4Client, target: WatchTarget) -> None:
        """Sigue una conversión hasta que termine, registrándola mientras tanto.

        Args:
            host (str): Dirección de la PS5.
            client (Lz4Client): Cliente emparejado.
            target (WatchTarget): Conversión a seguir.
        """
        follower = JobFollower(host, client, self._deps, self._emit)
        with self._lock:
            self._followers.add(follower)
        try:
            follower.run(target)
        finally:
            with self._lock:
                self._followers.discard(follower)

    def stop_all(self) -> None:
        """Pide a todos los seguimientos activos que terminen."""
        with self._lock:
            followers = list(self._followers)
        for follower in followers:
            follower.stop()
