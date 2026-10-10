"""Localiza el juego dentro de lo que el usuario arrastra y crea el trabajo."""
from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.config import (
    GAME_ROOT_MARKER,
    GAME_ROOT_SEARCH_DEPTH,
    IMAGE_EXTENSIONS,
    IMAGE_SEARCH_DEPTH,
    OUTPUT_EXTENSION,
)
from ffpfsc_converter.domain.models import ConversionJob
from ffpfsc_converter.errors import GameNotFoundError, SourceNotFoundError, UnsupportedFormatError


def is_image_file(path: Path) -> bool:
    """Indica si una ruta tiene extensión de imagen de juego soportada.

    Args:
        path (Path): Ruta a comprobar (no se accede al disco).

    Returns:
        bool: ``True`` si la extensión es ``.exfat`` o ``.ffpkg`` (sin distinguir mayúsculas).
    """
    return path.suffix.lower() in IMAGE_EXTENSIONS


def find_game_root(path: Path, max_depth: int = GAME_ROOT_SEARCH_DEPTH) -> Path | None:
    """Busca la carpeta que contiene ``eboot.bin``, la raíz real del juego.

    Args:
        path (Path): Carpeta desde la que se inicia la búsqueda.
        max_depth (int): Niveles de subcarpetas que se pueden recorrer.

    Returns:
        Path | None: Primera carpeta (en orden alfabético) con ``eboot.bin``, o
        ``None`` si no se encuentra.
    """
    if (path / GAME_ROOT_MARKER).is_file():
        return path
    if max_depth == 0:
        return None
    try:
        subdirs = sorted(p for p in path.iterdir() if p.is_dir())
    except OSError:
        return None
    for sub in subdirs:
        found = find_game_root(sub, max_depth - 1)
        if found:
            return found
    return None


def find_image_file(path: Path, max_depth: int = IMAGE_SEARCH_DEPTH) -> Path | None:
    """Busca una imagen ``.exfat``/``.ffpkg`` dentro de una carpeta.

    Args:
        path (Path): Carpeta en la que se busca.
        max_depth (int): Niveles de subcarpetas que se pueden recorrer.

    Returns:
        Path | None: La imagen más grande encontrada, o ``None`` si no hay ninguna.
    """
    found: list[Path] = []

    def walk(directory: Path, depth: int) -> None:
        """Acumula en ``found`` las imágenes de una carpeta y sus subcarpetas.

        Args:
            directory (Path): Carpeta a recorrer.
            depth (int): Niveles restantes que se pueden descender.
        """
        try:
            for child in directory.iterdir():
                if child.is_file() and is_image_file(child):
                    found.append(child)
                elif child.is_dir() and depth > 0:
                    walk(child, depth - 1)
        except OSError:
            pass

    walk(path, max_depth)
    return max(found, key=lambda p: p.stat().st_size) if found else None


def resolve_game_root(path: Path) -> Path:
    """Determina qué debe empaquetarse a partir de la ruta agregada.

    Args:
        path (Path): Carpeta o imagen que agregó el usuario.

    Returns:
        Path: Carpeta que contiene ``eboot.bin`` o imagen ``.exfat``/``.ffpkg``.

    Raises:
        SourceNotFoundError: Si la ruta no existe.
        UnsupportedFormatError: Si es un archivo que no es una imagen soportada.
        GameNotFoundError: Si es una carpeta sin un juego reconocible.
    """
    if path.is_file():
        if not is_image_file(path):
            raise UnsupportedFormatError(path)
        return path
    if path.is_dir():
        root = find_game_root(path) or find_image_file(path)
        if root is None:
            raise GameNotFoundError(path)
        return root
    raise SourceNotFoundError(path)


def output_path_for(source: Path, output_dir: Path | None) -> Path:
    """Calcula la ruta del ``.ffpfsc`` que se generará.

    Args:
        source (Path): Ruta que agregó el usuario (carpeta o imagen).
        output_dir (Path | None): Carpeta de destino; ``None`` = junto al origen.

    Returns:
        Path: Ruta de salida con el nombre del origen y extensión ``.ffpfsc``.
    """
    base = source.stem if source.is_file() else source.name
    return (output_dir or source.parent) / f"{base}{OUTPUT_EXTENSION}"


def create_job(source: Path, output_dir: Path | None = None) -> ConversionJob:
    """Crea un trabajo de conversión para la ruta agregada por el usuario.

    Args:
        source (Path): Carpeta o imagen que agregó el usuario.
        output_dir (Path | None): Carpeta de destino; ``None`` = junto al origen.

    Returns:
        ConversionJob: Trabajo en estado ``QUEUED``, aún sin analizar.

    Raises:
        SourceNotFoundError: Si la ruta no existe.
        UnsupportedFormatError: Si es un archivo que no es una imagen soportada.
        GameNotFoundError: Si es una carpeta sin un juego reconocible.
    """
    game_root = resolve_game_root(source)
    return ConversionJob(source, game_root, output_path_for(source, output_dir))
