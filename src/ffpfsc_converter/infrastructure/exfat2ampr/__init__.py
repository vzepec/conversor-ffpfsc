"""Cliente de exfat2ampr: compresión de juegos a AMPR LZ4 dentro de la PS5.

API pública:

- :class:`E2aClient`: órdenes a la API HTTP del motor (puerto 6972).
- :class:`E2aHttpError`: respuesta de error del motor (``status``, ``code``, ``error``).
- :func:`send_elf`: envía ``exfat2ampr.elf`` al cargador de ELF (puerto 9021).
"""
from __future__ import annotations

from ffpfsc_converter.infrastructure.exfat2ampr.client import E2aClient
from ffpfsc_converter.infrastructure.exfat2ampr.elf_loader import send_elf
from ffpfsc_converter.infrastructure.exfat2ampr.transport import E2aHttpError

__all__ = ["E2aClient", "E2aHttpError", "send_elf"]
