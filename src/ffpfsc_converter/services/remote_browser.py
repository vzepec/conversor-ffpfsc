"""Navegación por los archivos de la PS5 en un hilo de fondo.

Las órdenes (conectar, abrir carpeta, desconectar) se encolan y se ejecutan de
una en una en un único hilo, porque una sesión FTP no admite operaciones
simultáneas. Cada resultado se publica como evento.
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from ffpfsc_converter.config import PS5_START_PATH
from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.domain.remote_events import (
    FtpLoginRefused,
    RemoteConnected,
    RemoteDisconnected,
    RemoteError,
    RemoteListing,
)
from ffpfsc_converter.infrastructure.ftp import FTP_ERRORS, FtpClient
from ffpfsc_converter.infrastructure.ftp.errors import is_login_refused
from ffpfsc_converter.services.remote_client import ClientFactory, RemoteClient
from ffpfsc_converter.services.remote_errors import describe_error, is_connection_lost

_NOT_CONNECTED = "No hay conexión con la PS5. Pulsa «Conectar»."


class RemoteBrowser:
    """Explora la PS5 sin bloquear la interfaz."""

    def __init__(self, emit: EventSink, client_factory: ClientFactory = FtpClient) -> None:
        """Prepara el explorador sin conectarse.

        Args:
            emit (EventSink): Destino de los eventos (seguro entre hilos).
            client_factory (ClientFactory): Crea el cliente remoto para una consola.
        """
        self._emit = emit
        self._factory = client_factory
        self._client: RemoteClient | None = None
        self._target: ConsoleTarget | None = None
        self._commands: queue.Queue[Callable[[], None]] = queue.Queue()
        self._worker: threading.Thread | None = None

    @property
    def is_connected(self) -> bool:
        """Indica si hay una sesión abierta con la PS5.

        Returns:
            bool: ``True`` tras ``RemoteConnected`` y hasta ``RemoteDisconnected``.
        """
        return self._client is not None

    def connect(self, target: ConsoleTarget, start_path: str | None = None) -> None:
        """Encola la conexión con una consola y la apertura de una carpeta.

        Args:
            target (ConsoleTarget): Consola a la que conectarse.
            start_path (str | None): Carpeta a abrir; ``None`` = la inicial de la config.
        """
        self._submit(lambda: self._do_connect(target, start_path or PS5_START_PATH))

    def open(self, path: str) -> None:
        """Encola el listado de una carpeta remota.

        Args:
            path (str): Carpeta remota absoluta.
        """
        self._submit(lambda: self._do_list(path))

    def disconnect(self) -> None:
        """Encola el cierre de la conexión."""
        self._submit(self._drop)

    def wait_idle(self) -> None:
        """Espera a que se ejecuten todas las órdenes pendientes (para tests)."""
        self._commands.join()

    def _submit(self, command: Callable[[], None]) -> None:
        """Encola una orden y arranca el hilo de trabajo si aún no existe.

        Args:
            command (Callable[[], None]): Orden a ejecutar en el hilo de trabajo.
        """
        if self._worker is None:
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()
        self._commands.put(command)

    def _loop(self) -> None:
        """Ejecuta las órdenes encoladas, una tras otra, para siempre."""
        while True:
            command = self._commands.get()
            try:
                command()
            finally:
                self._commands.task_done()

    def _do_connect(self, target: ConsoleTarget, start_path: str) -> None:
        """Se conecta a la consola y abre una carpeta (o la raíz si no existe).

        Args:
            target (ConsoleTarget): Consola a la que conectarse.
            start_path (str): Carpeta a abrir.
        """
        self._drop(notify=False)
        client = self._factory(target)
        try:
            client.connect()
        except FTP_ERRORS as exc:
            client.close()
            if is_login_refused(exc):
                self._emit(FtpLoginRefused(target))
            else:
                self._emit(RemoteError(describe_error(exc, target, "conectar")))
            return
        self._client, self._target = client, target
        self._emit(RemoteConnected(target))
        self._do_list(start_path, fallback="/")

    def _do_list(self, path: str, fallback: str | None = None) -> None:
        """Lista una carpeta y publica el resultado o el error.

        Args:
            path (str): Carpeta remota absoluta.
            fallback (str | None): Carpeta alternativa si el servidor rechaza ``path``.
        """
        client, target = self._client, self._target
        if client is None or target is None:
            self._emit(RemoteError(_NOT_CONNECTED))
            return
        try:
            entries = client.list_dir(path)
        except FTP_ERRORS as exc:
            if fallback is not None and not is_connection_lost(exc):
                self._do_list(fallback)
                return
            self._emit(RemoteError(describe_error(exc, target, f"abrir {path}")))
            if is_connection_lost(exc):
                self._drop()
            return
        self._emit(RemoteListing(path, tuple(entries)))

    def _drop(self, notify: bool = True) -> None:
        """Cierra la sesión actual, si existe.

        Args:
            notify (bool): ``True`` para publicar ``RemoteDisconnected``.
        """
        client, self._client = self._client, None
        if client is None:
            return
        client.close()
        if notify:
            self._emit(RemoteDisconnected())
