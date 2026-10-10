"""Lectura de metadatos e imágenes exFAT mediante la API interna de MkPFS.

Los imports de ``mkpfs`` son diferidos para que el resto del paquete pueda
importarse (por ejemplo, en los tests) aunque MkPFS no esté instalado.
"""
from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.domain.models import GameInfo


def read_metadata(target: Path) -> GameInfo:
    """Lee los metadatos del juego con el lector de MkPFS.

    Args:
        target (Path): Carpeta de juego, imagen ``.exfat`` o ``.ffpkg``.

    Returns:
        GameInfo: Nombre, Title ID y versión según MkPFS.

    Raises:
        Exception: Cualquier error de MkPFS al leer un origen inválido o dañado.
    """
    from mkpfs.game_metadata import read_game_metadata

    meta = read_game_metadata(target)
    return GameInfo(meta.game_title, meta.title_id.strip("-"), meta.version)


def read_exfat_member(image: Path, rel_path: str, max_bytes: int) -> bytes | None:
    """Extrae el contenido de un archivo dentro de una imagen exFAT.

    Args:
        image (Path): Imagen ``.exfat``.
        rel_path (str): Ruta relativa buscada (sin distinguir mayúsculas).
        max_bytes (int): Tamaño máximo aceptado; los archivos mayores se ignoran.

    Returns:
        bytes | None: Contenido del archivo, o ``None`` si no existe o es demasiado grande.

    Raises:
        OSError: Si la imagen no se puede abrir o leer.
    """
    from mkpfs.exfat import ExfatReader

    wanted = rel_path.lower()
    with image.open("rb") as fh:
        reader = ExfatReader(fh)
        for entry in reader.iter_files():
            if entry.rel_path.lower() == wanted and entry.length < max_bytes:
                return b"".join(reader.read_file(entry))
    return None
