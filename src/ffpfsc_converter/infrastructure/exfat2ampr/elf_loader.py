"""Envío de un ELF al cargador de la PS5 (etaHEN/elfldr, puerto 9021).

El cargador recibe el binario completo por una conexión TCP y lo ejecuta al
cerrarse la conexión; no responde nada. Así se arranca exfat2ampr cuando no está
corriendo.
"""
from __future__ import annotations

import socket
from pathlib import Path

from ffpfsc_converter.config import ELF_LOADER_PORT, ELF_SEND_TIMEOUT_SECONDS


def send_elf(host: str, elf: Path, port: int = ELF_LOADER_PORT,
             timeout: float = ELF_SEND_TIMEOUT_SECONDS) -> None:
    """Envía un archivo ELF completo al cargador de la PS5 y cierra la conexión.

    El archivo se abre antes de conectar para no dejar al cargador esperando un
    binario que no llegará.

    Args:
        host (str): Dirección de la PS5.
        elf (Path): Archivo ``.elf`` local (por ejemplo ``exfat2ampr.elf``).
        port (int): Puerto del cargador de ELF.
        timeout (float): Segundos de espera para conectar y para cada envío.

    Raises:
        OSError: Si el archivo no existe o no se puede leer, si el cargador no
            acepta la conexión o si esta se corta durante el envío.
    """
    with elf.open("rb") as handle, socket.create_connection((host, port), timeout) as sock:
        sock.sendfile(handle)
        sock.shutdown(socket.SHUT_WR)
