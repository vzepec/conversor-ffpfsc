"""Textos que muestra la interfaz. Funciones puras, sin tkinter (testeables)."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote, urlparse

from ffpfsc_converter.domain.models import (
    CompressionPreset,
    ConversionJob,
    ConversionResult,
    GameInfo,
    ProgressUpdate,
)

QUEUED_TEXT = "En cola"
RUNNING_TEXT = "Convirtiendo…"
PENDING_TEXT = "analizando…"
_SIZE_UNITS = ("B", "KB", "MB", "GB")
_LAST_SIZE_UNIT = "TB"
_PHASE_NAMES = {
    "compress": "Comprimiendo",
    "write": "Escribiendo",
    "scan": "Escaneando",
    "verify": "Verificando",
}


def format_size(n: float) -> str:
    """Convierte bytes en un tamaño legible en base 1024.

    Args:
        n (float): Cantidad de bytes.

    Returns:
        str: Tamaño con un decimal y unidad, por ejemplo ``"1.5 KB"``.
    """
    for unit in _SIZE_UNITS:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} {_LAST_SIZE_UNIT}"


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


def progress_text(progress: ProgressUpdate) -> str:
    """Formatea el progreso de MkPFS con la fase en español.

    Args:
        progress (ProgressUpdate): Progreso informado por MkPFS.

    Returns:
        str: Por ejemplo ``"Comprimiendo: 37%  —  512.3 MB/s"``.
    """
    phase = _PHASE_NAMES.get(progress.phase, progress.phase)
    text = f"{phase}: {progress.percent}%"
    return f"{text}  —  {progress.speed}" if progress.speed else text


def result_text(job: ConversionJob, result: ConversionResult) -> str:
    """Formatea el resultado final de una conversión.

    Args:
        job (ConversionJob): Trabajo terminado.
        result (ConversionResult): Resultado de la conversión.

    Returns:
        str: Tamaño, ahorro y duración si tuvo éxito; motivo si no.
    """
    if result.succeeded:
        saved = savings_text(job.size, result.output_size)
        minutes = result.elapsed_seconds / 60
        return f"✔ {format_size(result.output_size)} ({saved}) en {minutes:.1f} min"
    if result.cancelled:
        return "✖ Cancelado"
    return f"✖ Error ({result.message})"


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
