"""Operaciones tipadas del helper: unidades y espacio libre (SPEC §7).

``fs.volumes`` lista solo almacenamiento real: ``/data`` (interno), ``/mnt/usbN``
(USB) y ``/mnt/extN`` (M.2 o USB ampliado); el helper ya descarta ranuras vacías.

Las tareas largas (borrado recursivo, CRC32) están en
:mod:`~ffpfsc_converter.infrastructure.ava1.jobs`; ``delete_tree`` y ``JobStatus``
se reexportan aquí por compatibilidad.
"""
from __future__ import annotations

from dataclasses import dataclass

from ffpfsc_converter.domain.remote import StorageVolume
from ffpfsc_converter.infrastructure.ava1.codec import Decoder, Encoder
from ffpfsc_converter.infrastructure.ava1.jobs import JobStatus, delete_tree
from ffpfsc_converter.infrastructure.ava1.session import Ava1Session

__all__ = ["FreeSpace", "JobStatus", "delete_tree", "free_space", "list_volumes"]

METHOD_FS_VOLUMES = 32
METHOD_FS_FREESPACE = 44
_IMAGE_MOUNT_PREFIX = "/mnt/ps5upload/"  # imágenes .exfat/.ffpkg montadas por el helper


@dataclass(frozen=True)
class FreeSpace:
    """Espacio del disco de la PS5 que contiene una ruta.

    Attributes:
        usable (int): Bytes que una subida puede ocupar (libres menos el margen del helper).
        total (int): Capacidad del disco.
    """

    usable: int
    total: int


def list_volumes(session: Ava1Session) -> tuple[StorageVolume, ...]:
    """Lista las unidades de almacenamiento montadas en la PS5.

    Se omiten las imágenes que montó el helper (``source_image``): no son discos.

    Args:
        session (Ava1Session): Sesión emparejada.

    Returns:
        tuple[StorageVolume, ...]: Unidades en el orden que informa la consola.

    Raises:
        Ava1Refused: Si la consola rechaza la consulta.
        ConnectionError: Si se pierde la conexión.
        ValueError: Si la respuesta no es JSON válido.
    """
    reply = session.call_text(METHOD_FS_VOLUMES, {})
    volumes = []
    for item in reply.get("volumes", []):
        volume = _parse_volume(item)
        if volume is not None:
            volumes.append(volume)
    return tuple(volumes)


def _parse_volume(item: object) -> StorageVolume | None:
    """Convierte una entrada de ``fs.volumes`` en una unidad.

    Args:
        item (object): Entrada JSON de la lista ``volumes``.

    Returns:
        StorageVolume | None: La unidad, o ``None`` si es una imagen montada o está
        mal formada.
    """
    if not isinstance(item, dict) or item.get("source_image"):
        return None
    path, total, free = item.get("path"), item.get("total_bytes"), item.get("free_bytes")
    if not isinstance(path, str) or not isinstance(total, int) or not isinstance(free, int):
        return None
    if path.startswith(_IMAGE_MOUNT_PREFIX) or total <= 0:
        return None
    return StorageVolume(path, str(item.get("mount_from", "")), total, max(free, 0))


def free_space(session: Ava1Session, path: str) -> FreeSpace:
    """Consulta el espacio usable del disco que contiene una ruta de la PS5.

    Args:
        session (Ava1Session): Sesión emparejada.
        path (str): Ruta remota (se consulta su ancestro existente más cercano).

    Returns:
        FreeSpace: Espacio usable y capacidad.

    Raises:
        ConnectionError: Si la consola rechaza la consulta o se pierde la conexión.
    """
    d = Decoder(session.call(METHOD_FS_FREESPACE, Encoder().text(path).build()))
    usable, _free, total = d.u64(), d.u64(), d.u64()
    return FreeSpace(usable=usable, total=total)
