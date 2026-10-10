"""Reintentos automáticos ante cortes de conexión durante una transferencia.

Las transferencias se reanudan (``.part`` + ``REST``), así que reintentar es
reconectar y continuar. Solo se reintentan los fallos transitorios: los
definitivos (sin espacio, ruta protegida, credenciales) se informan de inmediato.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from ffpfsc_converter import config
from ffpfsc_converter.errors import ConverterError, DownloadCancelledError, TransientError
from ffpfsc_converter.infrastructure.ava1.handshake import Ava1Refused, WrongConsoleError
from ffpfsc_converter.infrastructure.ftp.errors import is_server_refusal

T = TypeVar("T")
_ERR_BUSY = 8
_WAIT_STEP_SECONDS = 0.25

#: Recibe ``(intento, intentos_máximos, error)`` antes de cada reintento.
RetryCallback = Callable[[int, int, BaseException], None]


def is_transient(exc: BaseException) -> bool:
    """Indica si un error puede resolverse reintentando.

    Args:
        exc (BaseException): Error capturado.

    Returns:
        bool: ``True`` para cortes de red, tiempos agotados y verificaciones fallidas;
        ``False`` para cancelaciones, rechazos del servidor y errores locales.
    """
    if isinstance(exc, TransientError):
        return True
    if isinstance(exc, (ConverterError, WrongConsoleError)):
        return False
    if isinstance(exc, Ava1Refused):
        return exc.code == _ERR_BUSY
    if is_server_refusal(exc):
        return False
    return isinstance(exc, (OSError, EOFError)) or type(exc).__module__ == "ftplib"


def with_retries(
    action: Callable[[], T],
    on_retry: RetryCallback,
    should_cancel: Callable[[], bool],
    delays: tuple[float, ...] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Ejecuta una acción y la reintenta tras fallos transitorios.

    Args:
        action (Callable[[], T]): Intento completo (conectar y transferir); debe ser reanudable.
        on_retry (RetryCallback): Se llama antes de cada reintento (para informar en la UI).
        should_cancel (Callable[[], bool]): Devuelve ``True`` si el usuario canceló.
        delays (tuple[float, ...] | None): Espera antes de cada reintento (su largo es el
            máximo); ``None`` usa ``RETRY_DELAYS_SECONDS`` de la configuración.
        sleep (Callable[[float], None]): Función de espera; los tests la sustituyen.

    Returns:
        T: Resultado del primer intento exitoso.

    Raises:
        DownloadCancelledError: Si se cancela durante la espera.
        BaseException: El último error si no es transitorio o se agotan los reintentos.
    """
    delays = config.RETRY_DELAYS_SECONDS if delays is None else delays
    for attempt, delay in enumerate((*delays, None), start=1):
        try:
            return action()
        except BaseException as exc:
            if delay is None or not is_transient(exc) or should_cancel():
                raise
            on_retry(attempt, len(delays), exc)
            _wait(delay, should_cancel, sleep)
    raise AssertionError("inalcanzable")  # el bucle siempre retorna o lanza


def _wait(seconds: float, should_cancel: Callable[[], bool],
          sleep: Callable[[float], None]) -> None:
    """Espera en pasos cortos para poder cancelar durante la pausa.

    Args:
        seconds (float): Tiempo total de espera.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si el usuario canceló.
        sleep (Callable[[float], None]): Función de espera.

    Raises:
        DownloadCancelledError: Si se cancela durante la espera.
    """
    waited = 0.0
    while waited < seconds:
        if should_cancel():
            raise DownloadCancelledError()
        sleep(_WAIT_STEP_SECONDS)
        waited += _WAIT_STEP_SECONDS
