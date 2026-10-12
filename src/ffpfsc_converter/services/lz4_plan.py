"""Decisiones puras de la compresión LZ4: qué juego es y dónde conviene guardarlo."""
from __future__ import annotations

from collections.abc import Sequence

from ffpfsc_converter.config import LZ4_SEPARATE_NAME_SUFFIX
from ffpfsc_converter.domain.lz4 import Lz4Destination, Lz4Source

_MOUNT_ROOT = "mnt"
_INTERNAL_KIND = "internal"


def normalize_remote(path: str) -> str:
    """Quita la barra final de una ruta remota (salvo en la raíz).

    Args:
        path (str): Ruta remota absoluta.

    Returns:
        str: La misma ruta sin ``/`` al final.
    """
    return path.rstrip("/") or "/"


def find_source(sources: Sequence[Lz4Source], entry_path: str) -> Lz4Source | None:
    """Busca, entre los juegos que ve exfat2ampr, el que eligió el usuario.

    Args:
        sources (Sequence[Lz4Source]): Juegos de ``/api/sources``.
        entry_path (str): Carpeta o imagen elegida en el explorador.

    Returns:
        Lz4Source | None: El juego con esa ruta, o ``None`` si exfat2ampr no lo reconoce.
    """
    wanted = normalize_remote(entry_path)
    return next((s for s in sources if normalize_remote(s.path) == wanted), None)


def mount_prefix(path: str) -> str:
    """Calcula la unidad a la que pertenece una ruta de la PS5.

    Args:
        path (str): Ruta remota absoluta (``/data/…``, ``/mnt/usb0/…``, ``/mnt/ext1/…``).

    Returns:
        str: Punto de montaje (``/data``, ``/mnt/usb0``…); ``/`` si la ruta está vacía.
    """
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "/"
    if parts[0] == _MOUNT_ROOT and len(parts) > 1:
        return f"/{parts[0]}/{parts[1]}"
    return f"/{parts[0]}"


def suggest_destination(
    destinations: Sequence[Lz4Destination], source_path: str
) -> Lz4Destination | None:
    """Elige el destino sugerido para el juego convertido.

    Prefiere la misma unidad que el original (no hay que mover datos entre
    discos); si no se puede escribir ahí, la interna, y si tampoco, la unidad
    escribible con más espacio libre.

    Args:
        destinations (Sequence[Lz4Destination]): Unidades de ``/api/destinations``.
        source_path (str): Ruta del juego original en la PS5.

    Returns:
        Lz4Destination | None: Destino sugerido, o ``None`` si ninguno admite escritura.
    """
    writable = [d for d in destinations if d.writable]
    origin = mount_prefix(source_path)
    same_drive = next((d for d in writable if mount_prefix(d.base) == origin), None)
    if same_drive is not None:
        return same_drive
    internal = next((d for d in writable if d.kind == _INTERNAL_KIND), None)
    if internal is not None:
        return internal
    return max(writable, key=lambda d: d.free, default=None)


def output_name(source: Lz4Source, dest_base: str) -> str:
    """Elige el nombre de la carpeta de salida para no pisar el original.

    exfat2ampr crea ``<destino>/<TITLE_ID>``; si esa ruta es el propio juego (o lo
    contiene, o está dentro de él), la conversión fallaría, así que se usa otra carpeta.

    Args:
        source (Lz4Source): Juego a convertir.
        dest_base (str): Carpeta de juegos de la unidad de destino.

    Returns:
        str: ``""`` para el nombre predeterminado (el Title ID), o
        ``<TITLE_ID>-LZ4`` si el predeterminado choca con el original.
    """
    default = normalize_remote(f"{dest_base.rstrip('/')}/{source.title_id}")
    original = normalize_remote(source.path)
    clash = (default == original or original.startswith(f"{default}/")
             or default.startswith(f"{original}/"))
    return f"{source.title_id}{LZ4_SEPARATE_NAME_SUFFIX}" if clash else ""
