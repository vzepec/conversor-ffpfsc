"""Consulta el espacio libre de las unidades de la PS5 (interno, USB y ampliado).

Usa ``fs.volumes`` del helper en una sesión AVA1 propia, fuera del hilo de la
interfaz. Si llega otra petición mientras una consulta está en curso, se repite
una sola vez al terminar, para que el resultado refleje el último cambio.
"""
from __future__ import annotations

import threading

from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.remote_events import StorageUpdated
from ffpfsc_converter.errors import ConverterError
from ffpfsc_converter.infrastructure.ava1.console import list_volumes
from ffpfsc_converter.services.console_access import ConsoleAccess, NotPairedError

_NOT_PAIRED = "la app no está emparejada con esta PS5"
_UNAVAILABLE = "no se pudo consultar"


class StorageMonitor:
    """Publica el espacio de las unidades de la PS5 cada vez que se le pide."""

    def __init__(self, emit: EventSink, access: ConsoleAccess) -> None:
        """Prepara el servicio.

        Args:
            emit (EventSink): Destino de los eventos.
            access (ConsoleAccess): Acceso AVA1 a la consola.
        """
        self._emit = emit
        self._access = access
        self._lock = threading.Lock()
        self._running = False
        self._pending: str | None = None

    def refresh(self, host: str) -> threading.Thread | None:
        """Consulta las unidades en un hilo de fondo y publica ``StorageUpdated``.

        Args:
            host (str): Dirección de la PS5.

        Returns:
            threading.Thread | None: Hilo iniciado, o ``None`` si ya había una consulta
            en curso (se repetirá al terminar).
        """
        with self._lock:
            if self._running:
                self._pending = host
                return None
            self._running = True
        thread = threading.Thread(target=self._loop, args=(host,), daemon=True)
        thread.start()
        return thread

    def _loop(self, host: str) -> None:
        """Consulta y repite mientras haya peticiones que llegaron durante la consulta.

        Args:
            host (str): Dirección de la PS5.
        """
        current: str | None = host
        while current is not None:
            self._emit(self._query(current))
            with self._lock:
                current, self._pending = self._pending, None
                self._running = current is not None

    def _query(self, host: str) -> StorageUpdated:
        """Abre una sesión, lista las unidades y la cierra.

        No pide código: si la app no está emparejada, informa el motivo sin molestar.

        Args:
            host (str): Dirección de la PS5.

        Returns:
            StorageUpdated: Unidades o motivo del fallo.
        """
        try:
            session = self._access.open_session(host)
            try:
                return StorageUpdated(list_volumes(session))
            finally:
                session.close()
        except NotPairedError:
            return StorageUpdated((), _NOT_PAIRED)
        except (OSError, ValueError, ConverterError):
            return StorageUpdated((), _UNAVAILABLE)
