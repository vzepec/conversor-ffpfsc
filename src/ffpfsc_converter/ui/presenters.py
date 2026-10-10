"""Textos que muestra la interfaz. Funciones puras, sin tkinter (testeables)."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote, urlparse

from ffpfsc_converter import __version__
from ffpfsc_converter.config import APP_TITLE
from ffpfsc_converter.domain.models import (
    CompressionPreset,
    ConversionJob,
    GameInfo,
)
from ffpfsc_converter.formatting import format_size

RUNNING_TEXT = "Convirtiendo…"
PENDING_TEXT = "analizando…"


def version_text(version: str = __version__) -> str:
    """Formatea la versión de la aplicación para mostrarla en la interfaz.

    Args:
        version (str): Versión en formato SemVer; por defecto, la instalada.

    Returns:
        str: Versión con prefijo, por ejemplo ``"v1.3.0"``.
    """
    return f"v{version}"


def window_title(version: str = __version__) -> str:
    """Genera el título de la ventana principal con la versión.

    Args:
        version (str): Versión en formato SemVer; por defecto, la instalada.

    Returns:
        str: Por ejemplo ``"Conversor FFPFSC (PS5) — v1.3.0"``.
    """
    return f"{APP_TITLE} — {version_text(version)}"


def savings_percent(original: int, final: int) -> float:
    """Calcula el porcentaje de reducción de tamaño.

    Args:
        original (int): Tamaño original en bytes.
        final (int): Tamaño final en bytes.

    Returns:
        float: Porcentaje ahorrado; negativo si el archivo crece y ``0`` si
        ``original`` es ``0``.
    """
    return (1 - final / original) * 100 if original else 0.0


def savings_text(original: int, final: int) -> str:
    """Formatea la variación de tamaño con su signo.

    Args:
        original (int): Tamaño original en bytes.
        final (int): Tamaño final en bytes.

    Returns:
        str: ``"−40%"`` si se reduce o ``"+3%"`` si crece.
    """
    pct = savings_percent(original, final)
    return f"−{pct:.0f}%" if pct >= 0 else f"+{-pct:.0f}%"


def game_info_text(info: GameInfo) -> str:
    """Formatea el nombre del juego con su Title ID y versión.

    Args:
        info (GameInfo): Metadatos del juego.

    Returns:
        str: Por ejemplo ``"Juego  (PPSA01234 · v01.000.000)"``, o
        ``"(sin nombre)"`` si no hay título.
    """
    title = info.title or "(sin nombre)"
    version = f"v{info.version}" if info.version else ""
    extra = " · ".join(x for x in (info.title_id, version) if x)
    return f"{title}  ({extra})" if extra else title


def source_display_name(job: ConversionJob) -> str:
    """Genera el nombre corto del origen para la tabla.

    Args:
        job (ConversionJob): Trabajo a mostrar.

    Returns:
        str: Nombre de lo que agregó el usuario; incluye la imagen si se
        encontró dentro de una carpeta (``"carpeta/imagen.exfat"``).
    """
    root, source = job.game_root, job.source
    if root == source or root.is_dir():
        return source.name
    return f"{source.name}/{root.name}"


def estimate_text(job: ConversionJob, level: int) -> str:
    """Formatea el peso final estimado para un nivel de compresión.

    Args:
        job (ConversionJob): Trabajo analizado.
        level (int): Nivel de compresión seleccionado.

    Returns:
        str: Por ejemplo ``"≈ 7.1 GB (−63%)"``, o ``PENDING_TEXT`` si aún no
        hay estimación.
    """
    estimate = job.estimate_for(level)
    if estimate is None:
        return PENDING_TEXT
    return f"≈ {format_size(estimate)} ({savings_text(job.size, estimate)})"


def estimates_summary(job: ConversionJob, presets: Iterable[CompressionPreset]) -> str:
    """Genera la línea de registro con la estimación de todos los modos.

    Args:
        job (ConversionJob): Trabajo analizado.
        presets (Iterable[CompressionPreset]): Modos para obtener los nombres cortos.

    Returns:
        str: Línea con el tamaño original y el estimado por modo.
    """
    names = {p.level: p.short_label for p in presets}
    detail = "  |  ".join(
        f"{names.get(level, level)}: ≈{format_size(size)}"
        for level, size in sorted(job.estimates.items())
    )
    return f"Estimación {job.source.name} ({format_size(job.size)}): {detail}"


def parse_dropped_item(item: str) -> Path:
    """Convierte un elemento soltado en la ventana en una ruta.

    Args:
        item (str): Ruta simple o URI ``file://`` con caracteres escapados.

    Returns:
        Path: Ruta local decodificada.
    """
    if item.startswith("file://"):
        return Path(unquote(urlparse(item).path))
    return Path(item)


@dataclass(frozen=True)
class ConnectionCard:
    """Contenido de la tarjeta de estado de la PS5 en la barra lateral.

    Attributes:
        state (str): ``"on"``, ``"busy"`` u ``"off"`` (color del punto).
        title (str): Texto principal.
        lines (tuple[str, ...]): Líneas de detalle.
    """

    state: str
    title: str
    lines: tuple[str, ...]


def connection_card(status: ConsoleStatus) -> ConnectionCard:
    """Resume el estado de la conexión con la PS5 para la barra lateral.

    Args:
        status (ConsoleStatus): Estado de la conexión.

    Returns:
        ConnectionCard: Estado, título y detalle.
    """
    if status.connected:
        first = status.text if status.busy else f"{status.host} · solo lectura"
        lines = tuple(x for x in (first, status.free_text) if x)
        return ConnectionCard("busy" if status.busy else "on", "PS5 conectada", lines)
    if status.busy:
        return ConnectionCard("busy", "Conectando…", (status.host,))
    return ConnectionCard("off", "Sin conexión", ("Vincúlala en la sección PS5",))


@dataclass(frozen=True)
class ConsoleStatus:
    """Estado de la conexión con la PS5 que muestran la barra lateral y la vista PS5.

    Attributes:
        connected (bool): ``True`` si hay sesión abierta.
        text (str): Último mensaje de estado (``"Subiendo a /data/homebrew…"``).
        busy (bool): ``True`` mientras se conecta o hay una operación que escribe.
        host (str): IP de la PS5.
        free_text (str): Espacio libre del disco interno (vacío si no se conoce).
    """

    connected: bool
    text: str
    busy: bool
    host: str
    free_text: str = ""


class Pill(NamedTuple):
    """Píldora de estado.

    Attributes:
        kind (str): ``"wait"``, ``"run"``, ``"ok"``, ``"warn"`` o ``"bad"``.
        label (str): Texto.
    """

    kind: str
    label: str


def connection_pill(status: ConsoleStatus) -> Pill | None:
    """Elige la píldora de la tarjeta de conexión de la vista PS5.

    Args:
        status (ConsoleStatus): Estado de la conexión.

    Returns:
        Pill | None: Solo lectura o la operación en curso; ``None`` si no hay nada que decir.
    """
    if status.busy:
        return Pill("run", status.text.rstrip("."))
    if status.connected:
        return Pill("wait", "FTP en solo lectura")
    if not status.host:
        return Pill("wait", "Escribe la IP de la PS5")
    return None
