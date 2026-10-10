"""Comprobaciones de red simples."""
from __future__ import annotations

import socket


def is_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Indica si un puerto TCP acepta conexiones.

    Args:
        host (str): Dirección del equipo.
        port (int): Puerto TCP.
        timeout (float): Segundos de espera.

    Returns:
        bool: ``True`` si la conexión se estableció.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
