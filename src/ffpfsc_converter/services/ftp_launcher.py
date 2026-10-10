"""Asegura que el FTP de la PS5 esté activo, iniciándolo con el helper si hace falta.

El servidor FTP de ps5upload no arranca solo: se inicia con el método AVA1
``ftp.start``. Este servicio lo inicia en **solo lectura** y con usuario y
contraseña aleatorios, para que nadie más en la red pueda usarlo para modificar
la consola. La primera vez pide el código de emparejamiento que muestra la PS5.
"""
from __future__ import annotations

import queue
import secrets
import threading
import time
from collections.abc import Callable

from ffpfsc_converter.config import (
    AVA1_CLIENT_NAME,
    AVA1_PORT,
    FTP_TIMEOUT_SECONDS,
    PAIRING_CODE_TIMEOUT_SECONDS,
)
from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.domain.remote_events import FtpReady, PairingCodeRequired, RemoteError
from ffpfsc_converter.infrastructure.ava1.session import METHOD_FTP_START, Ava1Session
from ffpfsc_converter.infrastructure.ava1.trust import TrustStore
from ffpfsc_converter.infrastructure.network import is_port_open
from ffpfsc_converter.infrastructure.settings_store import load_settings, save_settings
from ffpfsc_converter.services.launch_errors import describe_launch_error

_CREDENTIALS_KEY = "ftp_credentials"
_START_ATTEMPTS = 6
_START_RETRY_SECONDS = 0.5
SessionFactory = Callable[[str, int, float], Ava1Session]


class PairingCancelledError(Exception):
    """El usuario no ingresó el código de emparejamiento."""


class FtpLauncher:
    """Inicia el FTP de la PS5 en un hilo de fondo y avisa cuando está listo."""

    def __init__(
        self,
        emit: EventSink,
        trust: TrustStore,
        session_factory: SessionFactory = Ava1Session,
        probe: Callable[[str, int], bool] = is_port_open,
    ) -> None:
        """Prepara el servicio.

        Args:
            emit (EventSink): Destino de los eventos.
            trust (TrustStore): Identidad de la app y consolas emparejadas.
            session_factory (SessionFactory): Abre una sesión AVA1 (los tests usan un doble).
            probe (Callable[[str, int], bool]): Comprueba si un puerto está abierto.
        """
        self._emit = emit
        self._trust = trust
        self._factory = session_factory
        self._probe = probe
        self._codes: queue.Queue[str | None] = queue.Queue()

    def connect(self, host: str, ftp_port: int, restart: bool = False) -> threading.Thread:
        """Comprueba el FTP y, si no está activo (o ``restart``), lo inicia.

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
            user, password = _saved_credentials(host)
            self._emit(FtpReady(ConsoleTarget(host, ftp_port, user, password), started=False))
            return
        try:
            target = self._start_with_helper(host, ftp_port, restart)
        except PairingCancelledError:
            self._emit(RemoteError("Emparejamiento cancelado."))
        except (OSError, ValueError) as exc:
            self._emit(RemoteError(describe_launch_error(exc, host)))
        else:
            self._emit(FtpReady(target, started=True))

    def _start_with_helper(self, host: str, ftp_port: int, restart: bool) -> ConsoleTarget:
        """Se conecta al helper, se empareja si hace falta e inicia el FTP.

        Args:
            host (str): Dirección de la PS5.
            ftp_port (int): Puerto FTP deseado.
            restart (bool): ``True`` para detener antes un FTP ya iniciado.

        Returns:
            ConsoleTarget: Datos de conexión al FTP recién iniciado.

        Raises:
            PairingCancelledError: Si el usuario no ingresó el código.
            OSError: Si falla la comunicación con la PS5.
            ValueError: Si la PS5 rechaza el inicio del FTP.
        """
        session = self._factory(host, AVA1_PORT, FTP_TIMEOUT_SECONDS)
        try:
            known = self._trust.known_key(host)
            est = session.handshake(self._trust.identity(), AVA1_CLIENT_NAME, known)
            if est.needs_code:
                session.pair(self._ask_code(est.server_name or host))
            if est.needs_code or known is None:
                self._trust.remember(host, est.server_key, est.server_name)
            if restart:
                session.call_text(METHOD_FTP_START, {"port": 0})
            user, password = "ffpfsc", secrets.token_urlsafe(18)
            reply = _start_ftp(session, {
                "port": ftp_port, "root": "/", "readonly": True, "user": user, "pass": password,
            })
        finally:
            session.close()
        if not reply.get("ok"):
            raise ValueError(f"ftp_start:{reply.get('error', 'unknown')}")
        save_settings({_CREDENTIALS_KEY: {**_all_credentials(), host: [user, password]}})
        return ConsoleTarget(host, ftp_port, user, password)

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


def _start_ftp(session: Ava1Session, request: dict[str, object]) -> dict[str, object]:
    """Envía ``ftp.start`` y reintenta mientras el FTP anterior termina de cerrarse.

    Args:
        session (Ava1Session): Sesión AVA1 emparejada.
        request (dict[str, object]): Parámetros de ``ftp.start``.

    Returns:
        dict[str, object]: Respuesta JSON de la consola.
    """
    reply: dict[str, object] = {}
    for _ in range(_START_ATTEMPTS):
        reply = session.call_text(METHOD_FTP_START, request)
        if reply.get("error") != "stopping":
            break
        time.sleep(_START_RETRY_SECONDS)
    return reply


def _all_credentials() -> dict[str, list[str]]:
    """Lee las credenciales FTP guardadas por consola.

    Returns:
        dict[str, list[str]]: Dirección → ``[usuario, contraseña]``.
    """
    data = load_settings().get(_CREDENTIALS_KEY)
    return data if isinstance(data, dict) else {}


def _saved_credentials(host: str) -> tuple[str, str]:
    """Obtiene las credenciales con las que la app inició el FTP de una consola.

    Args:
        host (str): Dirección de la PS5.

    Returns:
        tuple[str, str]: Usuario y contraseña; vacíos si no hay (acceso anónimo).
    """
    pair = _all_credentials().get(host)
    return (pair[0], pair[1]) if isinstance(pair, list) and len(pair) == 2 else ("", "")
