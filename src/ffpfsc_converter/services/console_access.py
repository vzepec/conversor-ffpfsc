"""Sesiones AVA1 con la PS5 y control de su servidor FTP.

Compartido por el lanzador del FTP, el borrado remoto y el pipeline de
conversión: abre una sesión emparejada (pidiendo el código solo si hace falta)
e inicia el FTP con los permisos mínimos que necesite cada operación.
"""
from __future__ import annotations

import contextlib
import logging
import secrets
import time
from collections.abc import Callable, Iterator

from ffpfsc_converter import config
from ffpfsc_converter.config import AVA1_CLIENT_NAME, AVA1_PORT, FTP_TIMEOUT_SECONDS
from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.domain.remote_events import FtpReady, FtpRestoreFailed
from ffpfsc_converter.errors import ConverterError
from ffpfsc_converter.infrastructure.app_log import LOGGER_NAME
from ffpfsc_converter.infrastructure.ava1.session import METHOD_FTP_START, Ava1Session
from ffpfsc_converter.infrastructure.ava1.trust import TrustStore
from ffpfsc_converter.infrastructure.settings_store import load_settings, save_settings

_CREDENTIALS_KEY = "ftp_credentials"
_FTP_USER = "ffpfsc"
_START_ATTEMPTS = 6
_START_RETRY_SECONDS = 0.5

SessionFactory = Callable[[str, int, float], Ava1Session]


class NotPairedError(ConverterError):
    """La app aún no está emparejada con la consola."""

    def __init__(self) -> None:
        """Crea el error con un mensaje para el usuario."""
        super().__init__("La app no está emparejada con esta PS5. "
                         "Pulsa «Conectar» en la vista PS5 para emparejarla.")


class ConsoleAccess:
    """Abre sesiones AVA1 y controla el FTP de una consola."""

    def __init__(self, trust: TrustStore, session_factory: SessionFactory = Ava1Session) -> None:
        """Prepara el acceso.

        Args:
            trust (TrustStore): Identidad de la app y consolas emparejadas.
            session_factory (SessionFactory): Abre una sesión AVA1 (los tests usan un doble).
        """
        self._trust = trust
        self._factory = session_factory

    def open_session(
        self, host: str, ask_code: Callable[[str], str] | None = None
    ) -> Ava1Session:
        """Abre una sesión emparejada con la consola.

        Args:
            host (str): Dirección de la PS5.
            ask_code (Callable[[str], str] | None): Pide el código de emparejamiento
                (recibe el nombre de la consola); ``None`` si no se debe emparejar.

        Returns:
            Ava1Session: Sesión lista para llamar métodos; hay que cerrarla.

        Raises:
            NotPairedError: Si la consola pide código y no se puede preguntar.
            OSError: Si falla la comunicación (incluye rechazos ``Ava1Refused``).
        """
        session = self._factory(host, AVA1_PORT, FTP_TIMEOUT_SECONDS)
        try:
            known = self._trust.known_key(host)
            est = session.handshake(self._trust.identity(), AVA1_CLIENT_NAME, known)
            if est.needs_code:
                if ask_code is None:
                    raise NotPairedError()
                session.pair(ask_code(est.server_name or host))
            if est.needs_code or known is None:
                self._trust.remember(host, est.server_key, est.server_name)
        except BaseException:
            session.close()
            raise
        return session

    def start_ftp(
        self, session: Ava1Session, host: str, port: int, writable: bool, restart: bool
    ) -> ConsoleTarget:
        """Inicia el FTP con credenciales aleatorias nuevas.

        Args:
            session (Ava1Session): Sesión emparejada.
            host (str): Dirección de la PS5.
            port (int): Puerto FTP.
            writable (bool): ``True`` para permitir escritura; ``False`` = solo lectura.
            restart (bool): ``True`` para detener antes el FTP que esté corriendo.

        Returns:
            ConsoleTarget: Datos de conexión con las credenciales nuevas.

        Raises:
            ValueError: Si la consola no pudo iniciar el FTP.
            OSError: Si falla la comunicación.
        """
        if restart:
            session.call_text(METHOD_FTP_START, {"port": 0})
        password = secrets.token_urlsafe(18)
        request = {"port": port, "root": "/", "readonly": not writable,
                   "user": _FTP_USER, "pass": password}
        reply: dict[str, object] = {}
        for _ in range(_START_ATTEMPTS):
            reply = session.call_text(METHOD_FTP_START, request)
            if reply.get("error") != "stopping":
                break
            time.sleep(_START_RETRY_SECONDS)
        if not reply.get("ok"):
            raise ValueError(f"ftp_start:{reply.get('error', 'unknown')}")
        save_settings({_CREDENTIALS_KEY: {**_all_credentials(), host: [_FTP_USER, password]}})
        return ConsoleTarget(host, port, _FTP_USER, password)


#: Recibe el FTP de solo lectura restaurado, o ``None`` si no se pudo restaurar.
RestoreCallback = Callable[[ConsoleTarget | None], None]


@contextlib.contextmanager
def writable_ftp(
    access: ConsoleAccess, host: str, port: int, on_restored: RestoreCallback
) -> Iterator[ConsoleTarget]:
    """Activa la escritura en el FTP solo mientras dura el bloque ``with``.

    Al salir (también por error o cancelación) lo reinicia en solo lectura con
    credenciales nuevas, reintentando unas veces (tras un corte, la consola puede
    tardar en responder), y entrega el resultado a ``on_restored``.

    Args:
        access (ConsoleAccess): Acceso a la consola (ya emparejada).
        host (str): Dirección de la PS5.
        port (int): Puerto FTP.
        on_restored (RestoreCallback): Recibe el FTP de solo lectura, o ``None`` si no
            se pudo restaurar (nunca se ignora en silencio: la interfaz lo recupera).

    Yields:
        ConsoleTarget: Datos de conexión al FTP con escritura.
    """
    session = access.open_session(host)
    try:
        target = access.start_ftp(session, host, port, writable=True, restart=True)
    finally:
        session.close()
    try:
        yield target
    finally:
        on_restored(_restore_readonly(access, host, port))


def restore_notifier(emit: EventSink, host: str, port: int) -> RestoreCallback:
    """Crea el aviso de fin de escritura para la interfaz.

    Args:
        emit (EventSink): Cola de eventos.
        host (str): Dirección de la PS5.
        port (int): Puerto FTP.

    Returns:
        RestoreCallback: Publica ``FtpReady`` (reconectar en solo lectura) o
        ``FtpRestoreFailed`` (la interfaz recupera la conexión).
    """
    def notify(target: ConsoleTarget | None) -> None:
        """Publica el evento que corresponde al resultado.

        Args:
            target (ConsoleTarget | None): FTP de solo lectura, o ``None`` si falló.
        """
        emit(FtpReady(target, started=True) if target else FtpRestoreFailed(host, port))

    return notify


def _restore_readonly(access: ConsoleAccess, host: str, port: int) -> ConsoleTarget | None:
    """Reinicia el FTP en solo lectura, con reintentos.

    Args:
        access (ConsoleAccess): Acceso a la consola.
        host (str): Dirección de la PS5.
        port (int): Puerto FTP.

    Returns:
        ConsoleTarget | None: FTP de solo lectura, o ``None`` si no se pudo.
    """
    log = logging.getLogger(LOGGER_NAME)
    for attempt in range(1, config.FTP_RESTORE_ATTEMPTS + 1):
        try:
            session = access.open_session(host)
            try:
                return access.start_ftp(session, host, port, writable=False, restart=True)
            finally:
                session.close()
        except (OSError, ValueError, ConverterError) as exc:
            log.warning("No se pudo volver el FTP a solo lectura (intento %d de %d): %s",
                        attempt, config.FTP_RESTORE_ATTEMPTS, exc)
            if attempt < config.FTP_RESTORE_ATTEMPTS:
                time.sleep(config.FTP_RESTORE_RETRY_SECONDS)
    return None


def saved_target(host: str, port: int) -> ConsoleTarget:
    """Construye los datos de conexión con las credenciales que guardó la app.

    Args:
        host (str): Dirección de la PS5.
        port (int): Puerto FTP.

    Returns:
        ConsoleTarget: Con usuario y contraseña guardados, o vacíos (anónimo).
    """
    pair = _all_credentials().get(host)
    if isinstance(pair, list) and len(pair) == 2:
        return ConsoleTarget(host, port, pair[0], pair[1])
    return ConsoleTarget(host, port)


def _all_credentials() -> dict[str, list[str]]:
    """Lee las credenciales FTP guardadas por consola.

    Returns:
        dict[str, list[str]]: Dirección → ``[usuario, contraseña]``.
    """
    data = load_settings().get(_CREDENTIALS_KEY)
    return data if isinstance(data, dict) else {}
