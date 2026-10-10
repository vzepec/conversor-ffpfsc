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
    return path.suffix.lower() in IMAGE_EXTENSIONS


def find_game_root(path: Path, max_depth: int = GAME_ROOT_SEARCH_DEPTH) -> Path | None:
    """Devuelve la carpeta que contiene ``eboot.bin`` (la raíz real del juego)."""
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
    """Busca un .exfat/.ffpkg dentro de una carpeta y devuelve el más grande."""
    found: list[Path] = []

    def walk(directory: Path, depth: int) -> None:
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
    """Devuelve lo que debe empaquetarse para ``path``.

    Raises:
        SourceNotFoundError: la ruta no existe.
        UnsupportedFormatError: es un archivo que no es .exfat/.ffpkg.
        GameNotFoundError: es una carpeta sin juego reconocible.
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
    """Ruta del .ffpfsc: junto al origen salvo que se elija otra carpeta."""
    base = source.stem if source.is_file() else source.name
    return (output_dir or source.parent) / f"{base}{OUTPUT_EXTENSION}"


def create_job(source: Path, output_dir: Path | None = None) -> ConversionJob:
    """Crea un trabajo de conversión para la ruta agregada por el usuario."""
    game_root = resolve_game_root(source)
    return ConversionJob(source, game_root, output_path_for(source, output_dir))
