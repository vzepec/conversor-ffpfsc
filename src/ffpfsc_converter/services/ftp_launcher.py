"""Asegura que el FTP de la PS5 esté activo, iniciándolo con el helper si hace falta.

El servidor FTP de ps5upload no arranca solo: se inicia con el método AVA1
``ftp.start``. Para navegar y descargar se inicia en **solo lectura** y con
usuario y contraseña aleatorios, para que nadie más en la red pueda usarlo para
modificar la consola. La primera vez pide el código de emparejamiento.
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from ffpfsc_converter.config import PAIRING_CODE_TIMEOUT_SECONDS
from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.domain.remote_events import FtpReady, PairingCodeRequired, RemoteError
from ffpfsc_converter.infrastructure.ava1.trust import TrustStore
from ffpfsc_converter.infrastructure.network import is_port_open
from ffpfsc_converter.services.console_access import (
    ConsoleAccess,
    SessionFactory,
    saved_target,
)
from ffpfsc_converter.services.launch_errors import describe_launch_error


class PairingCancelledError(Exception):
    """El usuario no ingresó el código de emparejamiento."""


class FtpLauncher:
    """Inicia el FTP de la PS5 en un hilo de fondo y avisa cuando está listo."""

    def __init__(
        self,
        emit: EventSink,
        trust: TrustStore,
        session_factory: SessionFactory | None = None,
        probe: Callable[[str, int], bool] = is_port_open,
    ) -> None:
        """Prepara el servicio.

        Args:
            emit (EventSink): Destino de los eventos.
            trust (TrustStore): Identidad de la app y consolas emparejadas.
            session_factory (SessionFactory | None): Abre una sesión AVA1; ``None`` = real.
            probe (Callable[[str, int], bool]): Comprueba si un puerto está abierto.
        """
        self._emit = emit
        self.access = (ConsoleAccess(trust, session_factory) if session_factory
                       else ConsoleAccess(trust))
        self._probe = probe
        self._codes: queue.Queue[str | None] = queue.Queue()

    def connect(self, host: str, ftp_port: int, restart: bool = False) -> threading.Thread:
        """Comprueba el FTP y, si no está activo (o ``restart``), lo inicia en solo lectura.

        Args:
            host (str): Dirección de la PS5.
            ftp_port (int): Puerto FTP deseado.
            restart (bool): ``True`` para detenerlo y volver a iniciarlo con credenciales nuevas.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        thread = threading.Thread(target=self._run, args=(host, ftp_port, restart), daemon=True)
        thread.start()
        return thread

    def provide_code(self, code: str | None) -> None:
        """Entrega el código de emparejamiento escrito por el usuario.

        Args:
            code (str | None): Código de seis dígitos, o ``None`` si canceló.
        """
        self._codes.put(code)

    def _run(self, host: str, ftp_port: int, restart: bool) -> None:
        """Publica ``FtpReady`` o ``RemoteError`` según el resultado.

        Args:
            host (str): Dirección de la PS5.
            ftp_port (int): Puerto FTP deseado.
            restart (bool): ``True`` para reiniciar el FTP.
        """
        if not restart and self._probe(host, ftp_port):
            self._emit(FtpReady(saved_target(host, ftp_port), started=False))
            return
        try:
            target = self._start(host, ftp_port, restart)
        except PairingCancelledError:
            self._emit(RemoteError("Emparejamiento cancelado."))
        except (OSError, ValueError) as exc:
            self._emit(RemoteError(describe_launch_error(exc, host)))
        else:
            self._emit(FtpReady(target, started=True))

    def _start(self, host: str, ftp_port: int, restart: bool) -> ConsoleTarget:
        """Abre una sesión (emparejando si hace falta) e inicia el FTP en solo lectura.

        Args:
            host (str): Dirección de la PS5.
            ftp_port (int): Puerto FTP deseado.
            restart (bool): ``True`` para detener antes un FTP ya iniciado.

        Returns:
            ConsoleTarget: Datos de conexión al FTP.

        Raises:
            PairingCancelledError: Si el usuario no ingresó el código.
            OSError: Si falla la comunicación con la PS5.
            ValueError: Si la PS5 rechaza el inicio del FTP.
        """
        session = self.access.open_session(host, ask_code=self._ask_code)
        try:
            return self.access.start_ftp(session, host, ftp_port, writable=False,
                                         restart=restart)
        finally:
            session.close()

    def _ask_code(self, console_name: str) -> str:
        """Pide el código a la interfaz y espera la respuesta.

        Args:
            console_name (str): Nombre de la consola, para el mensaje.

        Returns:
            str: Código de seis dígitos.

        Raises:
            PairingCancelledError: Si el usuario canceló o no respondió a tiempo.
        """
        while not self._codes.empty():
            self._codes.get_nowait()
        self._emit(PairingCodeRequired(console_name))
        try:
            code = self._codes.get(timeout=PAIRING_CODE_TIMEOUT_SECONDS)
        except queue.Empty:
            code = None
        if not code:
            raise PairingCancelledError()
        return code.strip()
