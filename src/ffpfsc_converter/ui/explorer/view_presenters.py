"""Datos de presentación de la vista PS5: tarjetas, etiquetas, ruta y estados. Funciones puras."""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from ffpfsc_converter.config import IMAGE_EXTENSIONS, OUTPUT_EXTENSION, STORAGE_WARN_PERCENT
from ffpfsc_converter.domain.remote import RemoteEntry, StorageVolume
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.ui.explorer.presenters import volume_name

_TITLE_ID = re.compile(r"[A-Z]{4}\d{5}")
_GAMES_FOLDER = "homebrew"
_INTERNAL, _USB, _EXTENDED = "/data", "/mnt/usb", "/mnt/ext"
#: Ranuras que siempre se muestran: (nombre, punto de montaje, icono).
_EMPTY_SLOTS = (("Interno", _INTERNAL, "drive"), ("USB", f"{_USB}0", "usb"),
                ("Ampliado", f"{_EXTENDED}0", "drive"))


@dataclass(frozen=True)
class Badge:
    """Etiqueta de tipo junto al nombre de un elemento remoto.

    Attributes:
        text (str): Texto de la etiqueta.
        kind (str): Color: ``"wait"`` (neutro), ``"ok"`` o ``"warn"``.
    """

    text: str
    kind: str


@dataclass(frozen=True)
class DriveCard:
    """Tarjeta de una unidad de la PS5.

    Attributes:
        name (str): Nombre visible (``"Interno"``, ``"USB 1"``…).
        path (str): Punto de montaje.
        icon (str): Icono de la tarjeta.
        percent (float): Porcentaje usado (0-100).
        text (str): Espacio libre, o por qué no hay datos.
        is_available (bool): ``False`` si la unidad no está conectada.
        is_full (bool): ``True`` si queda poco espacio (barra en ámbar).
    """

    name: str
    path: str
    icon: str
    percent: float
    text: str
    is_available: bool
    is_full: bool


@dataclass(frozen=True)
class ActionStates:
    """Botones de la barra de acciones que se pueden usar.

    Attributes:
        download (bool): Descargar la selección.
        convert (bool): Comprimir y reemplazar el elemento elegido.
        upload (bool): Subir archivos a la carpeta abierta.
        delete (bool): Eliminar la selección.
        lz4 (bool): Comprimir en LZ4 dentro de la PS5 el elemento elegido (exfat2ampr).
    """

    download: bool
    convert: bool
    upload: bool
    delete: bool
    lz4: bool


def entry_badge(entry: RemoteEntry) -> Badge | None:
    """Clasifica un elemento remoto para mostrar su etiqueta.

    Args:
        entry (RemoteEntry): Elemento de la carpeta abierta.

    Returns:
        Badge | None: «Juego» (carpeta con Title ID o dentro de ``homebrew``),
        «Comprimido» (``.ffpfsc``), «Imagen» (``.exfat``/``.ffpkg``) o ``None``.
    """
    if entry.is_dir:
        in_games = PurePosixPath(entry.path).parent.name == _GAMES_FOLDER
        return Badge("Juego", "wait") if in_games or _TITLE_ID.search(entry.name) else None
    suffix = PurePosixPath(entry.name).suffix.lower()
    if suffix == OUTPUT_EXTENSION:
        return Badge("Comprimido", "ok")
    return Badge("Imagen", "warn") if suffix in IMAGE_EXTENSIONS else None


def path_crumbs(path: str) -> list[tuple[str, str]]:
    """Divide una ruta remota en tramos navegables.

    Args:
        path (str): Ruta absoluta POSIX.

    Returns:
        list[tuple[str, str]]: Pares (nombre, ruta hasta ese tramo), sin la raíz.
    """
    parts = [p for p in path.split("/") if p]
    return [(name, "/" + "/".join(parts[: i + 1])) for i, name in enumerate(parts)]


def drive_cards(volumes: Iterable[StorageVolume], connected: bool) -> list[DriveCard]:
    """Prepara las tarjetas de las unidades: interna, USB y ampliada.

    Las ranuras USB y ampliada sin unidad aparecen como «No conectado»,
    igual que la PS5 las muestra en su menú de almacenamiento.

    Args:
        volumes (Iterable[StorageVolume]): Unidades montadas.
        connected (bool): ``True`` si hay conexión con la PS5.

    Returns:
        list[DriveCard]: Interno primero y luego las ranuras en orden.
    """
    if not connected:
        return [DriveCard(name, path, icon, 0.0, "Sin conexión", False, False)
                for name, path, icon in _EMPTY_SLOTS]
    by_path = sorted(volumes, key=lambda v: (v.path != _INTERNAL, v.path))
    cards = [_volume_card(v) for v in by_path]
    for name, path, icon in _EMPTY_SLOTS[1:]:
        if not any(v.path.startswith(path.rstrip("0")) for v in by_path):
            cards.append(DriveCard(name, path, icon, 0.0, "No conectado", False, False))
    return cards


def _volume_card(volume: StorageVolume) -> DriveCard:
    """Crea la tarjeta de una unidad montada.

    Args:
        volume (StorageVolume): Unidad.

    Returns:
        DriveCard: Tarjeta con el porcentaje usado y el espacio libre.
    """
    total = max(volume.total_bytes, 1)
    percent = min(100.0, (total - volume.free_bytes) * 100 / total)
    icon = "usb" if volume.path.startswith(_USB) else "drive"
    text = f"{format_size(volume.free_bytes)} libres de {format_size(volume.total_bytes)}"
    return DriveCard(volume_name(volume), volume.path, icon, percent, text, True,
                     percent >= STORAGE_WARN_PERCENT)


def internal_free_text(volumes: Iterable[StorageVolume]) -> str:
    """Resume el espacio libre del disco interno para la barra lateral.

    Args:
        volumes (Iterable[StorageVolume]): Unidades montadas.

    Returns:
        str: Por ejemplo ``"66.9 GB libres en /data"``, o vacío si no se conoce.
    """
    for volume in volumes:
        if volume.path == _INTERNAL:
            return f"{format_size(volume.free_bytes)} libres en {_INTERNAL}"
    return ""


def selection_text(count: int, writing: bool = False) -> str:
    """Describe cuántos elementos hay seleccionados (o que la PS5 está ocupada).

    Args:
        count (int): Elementos seleccionados.
        writing (bool): ``True`` mientras se escribe en la PS5 (la navegación se pausa).

    Returns:
        str: ``"Nada seleccionado"``, ``"1 seleccionado"``, ``"N seleccionados"`` o el
        aviso de operación en curso.
    """
    if writing:
        return "Escribiendo en la PS5…"
    if count == 0:
        return "Nada seleccionado"
    return "1 seleccionado" if count == 1 else f"{count} seleccionados"


def action_states(connected: bool, writing: bool,
                  selected: Sequence[RemoteEntry]) -> ActionStates:
    """Decide qué acciones tienen sentido con la selección actual.

    Args:
        connected (bool): ``True`` si hay conexión.
        writing (bool): ``True`` mientras se escribe en la PS5 (todo queda en pausa).
        selected (Sequence[RemoteEntry]): Elementos seleccionados.

    Returns:
        ActionStates: Botones habilitados.
    """
    usable = connected and not writing
    one = len(selected) == 1
    convertible = one and (selected[0].is_dir
                           or PurePosixPath(selected[0].name).suffix.lower() in IMAGE_EXTENSIONS)
    return ActionStates(download=usable and bool(selected), convert=usable and convertible,
                        upload=usable, delete=usable and bool(selected),
                        lz4=usable and convertible)
