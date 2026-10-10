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
_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")
_PHASE_NAMES = {
    "compress": "Comprimiendo",
    "write": "Escribiendo",
    "scan": "Escaneando",
    "verify": "Verificando",
}


def format_size(n: float) -> str:
    """Tamaño legible en base 1024: ``1536`` → ``"1.5 KB"``."""
    for unit in _SIZE_UNITS:
        if n < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{n:.1f} {unit}"
        n /= 1024
    raise AssertionError("inalcanzable")


def savings_percent(original: int, final: int) -> float:
    return (1 - final / original) * 100 if original else 0.0


def savings_text(original: int, final: int) -> str:
    """Variación de tamaño: ``"−40%"`` si reduce, ``"+3%"`` si crece."""
    pct = savings_percent(original, final)
    return f"−{pct:.0f}%" if pct >= 0 else f"+{-pct:.0f}%"


def game_info_text(info: GameInfo) -> str:
    title = info.title or "(sin nombre)"
    version = f"v{info.version}" if info.version else ""
    extra = " · ".join(x for x in (info.title_id, version) if x)
    return f"{title}  ({extra})" if extra else title


def source_display_name(job: ConversionJob) -> str:
    """Nombre corto del origen; incluye la imagen si se encontró dentro de una carpeta."""
    root, source = job.game_root, job.source
    if root == source or root.is_dir():
        return source.name
    return f"{source.name}/{root.name}"


def estimate_text(job: ConversionJob, level: int) -> str:
    estimate = job.estimate_for(level)
    if estimate is None:
        return PENDING_TEXT
    return f"≈ {format_size(estimate)} ({savings_text(job.size, estimate)})"


def estimates_summary(job: ConversionJob, presets: Iterable[CompressionPreset]) -> str:
    """Línea de log con la estimación para todos los modos."""
    names = {p.level: p.short_label for p in presets}
    detail = "  |  ".join(
        f"{names.get(level, level)}: ≈{format_size(size)}"
        for level, size in sorted(job.estimates.items())
    )
    return f"Estimación {job.source.name} ({format_size(job.size)}): {detail}"


def progress_text(progress: ProgressUpdate) -> str:
    phase = _PHASE_NAMES.get(progress.phase, progress.phase)
    text = f"{phase}: {progress.percent}%"
    return f"{text}  —  {progress.speed}" if progress.speed else text


def result_text(job: ConversionJob, result: ConversionResult) -> str:
    if result.succeeded:
        saved = savings_text(job.size, result.output_size)
        minutes = result.elapsed_seconds / 60
        return f"✔ {format_size(result.output_size)} ({saved}) en {minutes:.1f} min"
    if result.cancelled:
        return "✖ Cancelado"
    return f"✖ Error ({result.message})"


def parse_dropped_item(item: str) -> Path:
    """Convierte un elemento soltado (ruta o URI ``file://``) en una ruta."""
    if item.startswith("file://"):
        return Path(unquote(urlparse(item).path))
    return Path(item)
