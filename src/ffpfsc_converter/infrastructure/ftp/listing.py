"""Interpretación de los listados FTP (``MLSD`` y, como respaldo, ``LIST``).

Funciones puras: no abren conexiones. Los nombres que llegan del servidor se
validan aquí, porque terminan convirtiéndose en rutas locales.
"""
from __future__ import annotations

import posixpath
from collections.abc import Iterable, Mapping

from ffpfsc_converter.domain.remote import RemoteEntry

_SPECIAL_NAMES = frozenset({"", ".", ".."})
_FORBIDDEN_CHARS = ("/", "\\", "\x00")
_LIST_MIN_FIELDS = 9


def is_safe_name(name: str) -> bool:
    """Indica si un nombre recibido del servidor es seguro como nombre de archivo.

    Rechaza ``.``, ``..`` y nombres con separadores de ruta, que permitirían
    escribir fuera de la carpeta de destino al descargar.

    Args:
        name (str): Nombre tal como lo envió el servidor.

    Returns:
        bool: ``True`` si se puede usar como un único componente de ruta.
    """
    return name not in _SPECIAL_NAMES and not any(c in name for c in _FORBIDDEN_CHARS)


def join_remote(parent: str, name: str) -> str:
    """Une una carpeta remota y un nombre en una ruta POSIX normalizada.

    Args:
        parent (str): Carpeta remota absoluta.
        name (str): Nombre del elemento.

    Returns:
        str: Ruta absoluta, por ejemplo ``/data/homebrew/juego.ffpfsc``.
    """
    return posixpath.normpath(posixpath.join(parent or "/", name))


def entries_from_mlsd(
    parent: str, rows: Iterable[tuple[str, Mapping[str, str]]]
) -> list[RemoteEntry]:
    """Convierte las filas de ``ftplib.FTP.mlsd`` en elementos remotos.

    Args:
        parent (str): Carpeta listada.
        rows (Iterable[tuple[str, Mapping[str, str]]]): Pares ``(nombre, hechos)``.

    Returns:
        list[RemoteEntry]: Elementos válidos, sin ``.``, ``..`` ni nombres inseguros.
    """
    entries: list[RemoteEntry] = []
    for name, facts in rows:
        kind = facts.get("type", "").lower()
        if kind in ("cdir", "pdir") or not is_safe_name(name):
            continue
        is_dir = kind == "dir"
        entries.append(RemoteEntry(
            name=name,
            path=join_remote(parent, name),
            is_dir=is_dir,
            size=0 if is_dir else _to_int(facts.get("size", "0")),
            modified=facts.get("modify", "")[:14],
        ))
    return entries


def parse_list_line(parent: str, line: str) -> RemoteEntry | None:
    """Interpreta una línea de ``LIST`` estilo Unix (``ls -l``).

    Args:
        parent (str): Carpeta listada.
        line (str): Línea, por ejemplo ``drwxr-xr-x 1 root root 512 Jan 1 2026 juegos``.

    Returns:
        RemoteEntry | None: El elemento, o ``None`` si la línea no se reconoce o
        el nombre no es seguro.
    """
    fields = line.split(None, _LIST_MIN_FIELDS - 1)
    if len(fields) < _LIST_MIN_FIELDS or fields[0][:1] not in ("d", "-", "l"):
        return None
    name = fields[-1]
    if not is_safe_name(name):
        return None
    is_dir = fields[0].startswith("d")
    return RemoteEntry(
        name=name,
        path=join_remote(parent, name),
        is_dir=is_dir,
        size=0 if is_dir else _to_int(fields[4]),
    )


def sort_entries(entries: Iterable[RemoteEntry]) -> list[RemoteEntry]:
    """Ordena los elementos como un explorador: carpetas primero y luego por nombre.

    Args:
        entries (Iterable[RemoteEntry]): Elementos a ordenar.

    Returns:
        list[RemoteEntry]: Nueva lista ordenada sin distinguir mayúsculas.
    """
    return sorted(entries, key=lambda e: (not e.is_dir, e.name.casefold()))


def _to_int(text: str) -> int:
    """Convierte un tamaño textual en entero, tolerando valores inválidos.

    Args:
        text (str): Texto con el número.

    Returns:
        int: El número, o ``0`` si no es válido.
    """
    try:
        return int(text)
    except ValueError:
        return 0
