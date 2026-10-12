"""Reconoce juegos en la PS5: carpetas de juego y las que ya están comprimidas en LZ4.

Una carpeta LZ4 (formato AMPR) se distingue por su índice de paquetes
(``ampr_assets.index``); para saberlo hay que listar la carpeta por dentro.
"""
from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath

from ffpfsc_converter.config import AMPR_ASSETS_INDEX, PS5_GAMES_FOLDER
from ffpfsc_converter.domain.remote import RemoteEntry
from ffpfsc_converter.services.remote_client import RemoteClient

_TITLE_ID = re.compile(r"[A-Z]{4}\d{5}")
ALREADY_LZ4_TEXT = "Este juego ya está comprimido en LZ4."


def looks_like_game(entry: RemoteEntry) -> bool:
    """Indica si una carpeta parece un juego.

    Args:
        entry (RemoteEntry): Elemento remoto.

    Returns:
        bool: ``True`` para carpetas dentro de ``homebrew`` o con un Title ID en el nombre.
    """
    if not entry.is_dir:
        return False
    return (PurePosixPath(entry.path).parent.name == PS5_GAMES_FOLDER
            or _TITLE_ID.search(entry.name) is not None)


def is_lz4_folder(client: RemoteClient, path: str) -> bool:
    """Indica si una carpeta de la PS5 ya está comprimida en LZ4.

    Args:
        client (RemoteClient): Cliente conectado.
        path (str): Carpeta remota.

    Returns:
        bool: ``True`` si contiene ``ampr_assets.index``.

    Raises:
        OSError: Si falla el listado (red o carpeta inaccesible).
    """
    return any(entry.name == AMPR_ASSETS_INDEX for entry in client.list_dir(path))


def mark_lz4_games(client: RemoteClient, entries: Sequence[RemoteEntry],
                   should_stop: Callable[[], bool]) -> tuple[RemoteEntry, ...] | None:
    """Revisa por dentro las carpetas de juego y marca las que ya están en LZ4.

    Args:
        client (RemoteClient): Cliente conectado.
        entries (Sequence[RemoteEntry]): Contenido de la carpeta abierta.
        should_stop (Callable[[], bool]): Devuelve ``True`` para dejar de revisar
            (por ejemplo, si el usuario abrió otra carpeta).

    Returns:
        tuple[RemoteEntry, ...] | None: Los mismos elementos con ``is_lz4`` marcado, o
        ``None`` si no se encontró ninguno o se dejó de revisar.

    Raises:
        OSError: Si falla un listado.
    """
    found: set[str] = set()
    for entry in entries:
        if should_stop():
            return None
        if looks_like_game(entry) and is_lz4_folder(client, entry.path):
            found.add(entry.path)
    if not found:
        return None
    return tuple(dataclasses.replace(e, is_lz4=True) if e.path in found else e for e in entries)
