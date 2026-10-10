"""Traduce errores de red y FTP en mensajes útiles para el usuario."""
from __future__ import annotations

from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.infrastructure.ftp.errors import (
    is_login_refused,
    is_server_refusal,
    is_unknown_host,
)


def describe_error(exc: BaseException, target: ConsoleTarget, action: str) -> str:
    """Explica un error de comunicación y qué revisar para resolverlo.

    Args:
        exc (BaseException): Error capturado.
        target (ConsoleTarget): Consola con la que se intentaba comunicar.
        action (str): Qué se intentaba hacer, en infinitivo (``"abrir /data"``).

    Returns:
        str: Mensaje en español listo para mostrar.
    """
    where = f"{target.host}:{target.port}"
    if isinstance(exc, ConnectionRefusedError):
        return (f"La PS5 ({where}) rechazó la conexión.\n\n"
                "Inicia el servidor FTP en la app de ps5upload (pantalla FTP Server → Start) "
                "y revisa que el puerto coincida.")
    if isinstance(exc, TimeoutError):
        return (f"La PS5 ({where}) no respondió a tiempo al {action}.\n\n"
                "Revisa la IP, que la consola esté encendida y en la misma red.")
    if is_unknown_host(exc):
        return f"No se encontró la dirección «{target.host}». Revisa la IP de la PS5."
    if is_login_refused(exc):
        return "La PS5 rechazó el usuario o la contraseña."
    if is_server_refusal(exc):
        return f"La PS5 no permitió {action}: {exc}"
    if isinstance(exc, (EOFError, OSError)):
        return (f"Se perdió la conexión con la PS5 ({where}) al {action}.\n\n"
                "Vuelve a conectar. Si la PS5 entró en reposo, "
                "inicia de nuevo el FTP en ps5upload.")
    return f"Error al {action}: {exc}"


def is_connection_lost(exc: BaseException) -> bool:
    """Indica si el error implica que la sesión ya no sirve.

    Args:
        exc (BaseException): Error capturado.

    Returns:
        bool: ``False`` solo para rechazos del servidor (la sesión sigue viva).
    """
    return not is_server_refusal(exc)
