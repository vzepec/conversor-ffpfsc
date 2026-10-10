"""Mensajes para los errores de las operaciones con el helper de ps5upload y su FTP."""
from __future__ import annotations

from ffpfsc_converter.errors import ConverterError
from ffpfsc_converter.infrastructure.ava1.handshake import Ava1Refused, WrongConsoleError
from ffpfsc_converter.infrastructure.ftp.errors import is_server_refusal

_ERR_PAIRING_CLOSED = 2
_ERR_BUSY = 8
_ERR_PATH = 9
_ERR_PAIRING_CODE = 19

_HELPER_HINT = "Revisa que el payload de ps5upload esté cargado en la PS5 (puerto 9120)."


def describe_launch_error(exc: BaseException, host: str, action: str = "iniciar el FTP") -> str:
    """Explica por qué falló una operación con la PS5 y qué hacer.

    Args:
        exc (BaseException): Error capturado.
        host (str): Dirección de la PS5.
        action (str): Qué se intentaba hacer, en infinitivo (``"borrar"``, ``"subir"``…).

    Returns:
        str: Mensaje en español listo para mostrar.
    """
    if isinstance(exc, ConverterError):
        return str(exc)
    if isinstance(exc, Ava1Refused):
        return _describe_refusal(exc, action)
    if isinstance(exc, WrongConsoleError):
        return (f"El equipo en {host} no es la PS5 con la que se emparejó la app.\n\n"
                "Si cambiaste de consola o reinstalaste el sistema, borra el archivo "
                "ava1_peers.json de la carpeta de ajustes y vuelve a emparejar.")
    if isinstance(exc, ConnectionRefusedError):
        return f"La PS5 ({host}) rechazó la conexión al {action}.\n\n{_HELPER_HINT}"
    if isinstance(exc, TimeoutError):
        return f"La PS5 ({host}) no respondió a tiempo al {action}.\n\nRevisa la IP y la red."
    if isinstance(exc, ValueError) and str(exc).startswith("ftp_start:"):
        return f"La PS5 no pudo iniciar el FTP ({str(exc).split(':', 1)[1]})."
    if is_server_refusal(exc):
        return f"La PS5 no permitió {action}: {exc}"
    if isinstance(exc, (EOFError, OSError)):
        return (f"Se perdió la conexión con la PS5 ({host}) al {action}.\n\n"
                "Si la PS5 entró en reposo, vuelve a cargar el payload y reintenta.")
    return f"No se pudo {action}: {exc}"


def _describe_refusal(exc: Ava1Refused, action: str) -> str:
    """Explica un rechazo del helper según su código AVA1.

    Args:
        exc (Ava1Refused): Rechazo recibido.
        action (str): Qué se intentaba hacer.

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
        return "La PS5 está ocupada. Espera un minuto y reintenta."
    if exc.code == _ERR_PATH:
        return (f"La PS5 no permite {action} esa ruta ({exc.reason}). Por seguridad no se "
                "pueden borrar raíces, carpetas de primer nivel ni puntos de montaje.")
    return f"La PS5 rechazó {action} (código {exc.code}): {exc.reason}"
