"""Textos de las filas de la vista Convertir. Funciones puras (testeables)."""
from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

from ffpfsc_converter.domain.models import (
    ConversionJob,
    ConversionResult,
    GameInfo,
    ProgressUpdate,
)
from ffpfsc_converter.formatting import PHASE_NAMES, format_eta, format_size
from ffpfsc_converter.ui.presenters import savings_text

_SEPARATOR = "  ·  "
#: Píldora y detalle de un ``.ffpfsc`` agregado ya comprimido.
READY_LABEL = "✓ Ya comprimido"
READY_DETAIL = "Listo para subir a la PS5"


class RowStatus(NamedTuple):
    """Estado de una fila de la cola.

    Attributes:
        kind (str): Tipo de píldora: ``"wait"``, ``"run"``, ``"ok"``, ``"warn"`` o ``"bad"``.
        label (str): Texto de la píldora.
        detail (str): Texto bajo la píldora.
    """

    kind: str
    label: str
    detail: str


def game_title(info: GameInfo) -> str:
    """Obtiene el nombre a mostrar del juego.

    Args:
        info (GameInfo): Metadatos del juego.

    Returns:
        str: El título, o ``"(sin nombre)"`` si no se pudo leer.
    """
    return info.title or "(sin nombre)"


def game_meta(info: GameInfo, fallback: str) -> str:
    """Obtiene la línea secundaria: Title ID y versión.

    Args:
        info (GameInfo): Metadatos del juego.
        fallback (str): Texto si no hay Title ID ni versión (por ejemplo, la carpeta).

    Returns:
        str: Por ejemplo ``"PPSA01234 · v01.002"``.
    """
    version = f"v{info.version}" if info.version else ""
    return " · ".join(x for x in (info.title_id, version) if x) or fallback


class SizeText(NamedTuple):
    """Tamaño de un juego en su fila.

    Attributes:
        original (str): Tamaño original con flecha (``"48.2 GB →"``) o el estado del análisis.
        estimate (str): Peso estimado (``"≈ 21.7 GB"``); vacío mientras se calcula.
        note (str): Ahorro estimado o estado de la estimación.
    """

    original: str
    estimate: str
    note: str


def size_lines(job: ConversionJob, level: int, performance: bool = False) -> SizeText:
    """Genera el tamaño original, el estimado y el ahorro de un juego.

    Args:
        job (ConversionJob): Juego (con tamaño y estimaciones si ya se analizó).
        level (int): Nivel de compresión elegido.
        performance (bool): ``True`` si está activo «Rendimiento en la PS5».

    Returns:
        SizeText: Por ejemplo ``("48.2 GB →", "≈ 21.7 GB", "−55% estimado")``.
    """
    if not job.size:
        return SizeText("calculando…", "", "")
    if job.already_compressed:
        return SizeText(format_size(job.size), "", "ya comprimido")
    estimate = job.estimate_for(level, performance)
    if estimate is None:
        return SizeText(format_size(job.size), "", "estimando…")
    return SizeText(f"{format_size(job.size)} →", f"≈ {format_size(estimate)}",
                    f"{savings_text(job.size, estimate)} estimado")


def progress_status(progress: ProgressUpdate, eta: float | None) -> RowStatus:
    """Genera el estado de una fila mientras MkPFS trabaja.

    Args:
        progress (ProgressUpdate): Avance de MkPFS.
        eta (float | None): Segundos restantes estimados de la fase.

    Returns:
        RowStatus: Por ejemplo ``("run", "Comprimiendo · 37%", "512 MB/s  ·  quedan ≈ 2 min")``.
    """
    phase = PHASE_NAMES.get(progress.phase, progress.phase)
    detail = _SEPARATOR.join(x for x in (progress.speed or "", format_eta(eta)) if x)
    return RowStatus("run", f"{phase} · {progress.percent}%", detail)


def result_status(job: ConversionJob, result: ConversionResult) -> RowStatus:
    """Genera el estado final de una fila.

    Args:
        job (ConversionJob): Juego convertido.
        result (ConversionResult): Resultado.

    Returns:
        RowStatus: Listo con tamaño y tiempo, cancelado, o error con su motivo.
    """
    if result.succeeded:
        minutes = result.elapsed_seconds / 60
        detail = (f"{format_size(result.output_size)} "
                  f"({savings_text(job.size, result.output_size)}) en {minutes:.1f} min")
        return RowStatus("ok", "✓ Listo", detail)
    if result.cancelled:
        return RowStatus("warn", "Cancelado", "")
    return RowStatus("bad", "Error", result.message)


def upload_status(done: int, total: int, speed: str, eta: float | None) -> tuple[RowStatus, float]:
    """Genera el estado de una fila mientras se sube a la PS5.

    Args:
        done (int): Bytes enviados.
        total (int): Bytes totales.
        speed (str): Velocidad ya formateada (puede estar vacía).
        eta (float | None): Segundos restantes estimados.

    Returns:
        tuple[RowStatus, float]: Estado y porcentaje para la barra.
    """
    percent = min(100.0, done * 100 / total) if total else 100.0
    detail = _SEPARATOR.join(x for x in (speed, format_eta(eta)) if x)
    return RowStatus("run", f"Subiendo a la PS5 · {percent:.0f}%", detail), percent


def queue_summary(jobs: Iterable[ConversionJob], level: int, performance: bool = False) -> str:
    """Resume la cola: cantidad de juegos, tamaño total y estimado.

    Args:
        jobs (Iterable[ConversionJob]): Juegos de la cola.
        level (int): Nivel de compresión elegido.
        performance (bool): ``True`` si está activo «Rendimiento en la PS5».

    Returns:
        str: Por ejemplo ``"3 juegos  ·  69.6 GB → ≈ 31.4 GB"``, o vacío si no hay juegos.
    """
    items = list(jobs)
    if not items:
        return ""
    count = f"{len(items)} juego" + ("s" if len(items) != 1 else "")
    sized = [j for j in items if j.size]
    finals = [j.size if j.already_compressed else j.estimate_for(level, performance)
              for j in sized]
    if not sized or any(final is None for final in finals):
        return count
    total = sum(j.size for j in sized)
    estimate = sum(final or 0 for final in finals)
    return f"{count}{_SEPARATOR}{format_size(total)} → ≈ {format_size(estimate)}"
