"""Clasificación de los errores de ``ftplib`` y de red.

Los servicios usan estas funciones en lugar de importar ``ftplib`` o
``socket`` directamente.
"""
from __future__ import annotations

import ftplib
import socket

#: Excepciones que puede lanzar cualquier operación FTP.
FTP_ERRORS: tuple[type[BaseException], ...] = (*ftplib.all_errors, ConnectionError)


def is_server_refusal(exc: BaseException) -> bool:
    """Indica si el servidor rechazó la orden pero la sesión sigue abierta.

    Args:
        exc (BaseException): Error capturado.

    Returns:
        bool: ``True`` para respuestas FTP 5xx (por ejemplo, carpeta inexistente).
    """
    return isinstance(exc, ftplib.error_perm)


def is_login_refused(exc: BaseException) -> bool:
    """Indica si el servidor rechazó el usuario o la contraseña.

    Args:
        exc (BaseException): Error capturado.

    Returns:
        bool: ``True`` para la respuesta FTP 530.
    """
    return is_server_refusal(exc) and str(exc).startswith("530")


def is_unknown_host(exc: BaseException) -> bool:
    """Indica si no se pudo resolver el nombre o la IP de la consola.

    Args:
        exc (BaseException): Error capturado.

    Returns:
        bool: ``True`` si el error es de resolución de nombres.
    """
    return isinstance(exc, socket.gaierror)
