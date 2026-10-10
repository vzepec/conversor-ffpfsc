"""Mensajes para los errores al iniciar el FTP mediante el helper de ps5upload."""
from __future__ import annotations

from ffpfsc_converter.infrastructure.ava1.handshake import Ava1Refused, WrongConsoleError

_ERR_PAIRING_CLOSED = 2
_ERR_BUSY = 8
_ERR_PAIRING_CODE = 19

_HELPER_HINT = "Revisa que el payload de ps5upload esté cargado en la PS5 (puerto 9120)."


def describe_launch_error(exc: BaseException, host: str) -> str:
    """Explica por qué no se pudo iniciar el FTP y qué hacer.

    Args:
        exc (BaseException): Error capturado.
        host (str): Dirección de la PS5.

    Returns:
        str: Mensaje en español listo para mostrar.
    """
    if isinstance(exc, Ava1Refused):
        return _describe_refusal(exc)
    if isinstance(exc, WrongConsoleError):
        return (f"El equipo en {host} no es la PS5 con la que se emparejó la app.\n\n"
                "Si cambiaste de consola o reinstalaste el sistema, borra el archivo "
                "ava1_peers.json de la carpeta de ajustes y vuelve a emparejar.")
    if isinstance(exc, ConnectionRefusedError):
        return f"La PS5 ({host}) no respondió en el puerto 9120.\n\n{_HELPER_HINT}"
    if isinstance(exc, TimeoutError):
        return f"La PS5 ({host}) no respondió a tiempo.\n\nRevisa la IP y la red. {_HELPER_HINT}"
    if isinstance(exc, ValueError) and str(exc).startswith("ftp_start:"):
        return f"La PS5 no pudo iniciar el FTP ({str(exc).split(':', 1)[1]})."
    return f"No se pudo iniciar el FTP en la PS5: {exc}"


def _describe_refusal(exc: Ava1Refused) -> str:
    """Explica un rechazo del helper según su código AVA1.

    Args:
        exc (Ava1Refused): Rechazo recibido.

    Returns:
        str: Mensaje en español.
    """
    if exc.code == _ERR_PAIRING_CLOSED:
        return ("La PS5 no acepta emparejamientos nuevos en este momento.\n\n"
                "Vuelve a cargar el payload de ps5upload y pulsa «Conectar» dentro de los "
                "5 minutos siguientes. La PS5 mostrará un código de 6 dígitos.")
    if exc.code == _ERR_PAIRING_CODE:
        return "La PS5 no aceptó el código. Pulsa «Conectar» de nuevo y escribe el código nuevo."
    if exc.code == _ERR_BUSY:
        return "La PS5 está ocupada con otros emparejamientos. Espera un minuto y reintenta."
    return f"La PS5 rechazó la operación (código {exc.code}): {exc.reason}"
