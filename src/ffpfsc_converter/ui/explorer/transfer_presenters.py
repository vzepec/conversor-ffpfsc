"""Textos del panel de transferencias de la vista PS5 (incluido "comprimir y reemplazar")."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from ffpfsc_converter.domain.pipeline import PipelineResult, PipelineStage
from ffpfsc_converter.domain.remote import DownloadResult
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.ui.explorer.presenters import (
    PIPELINE_STEPS,
    STAGE_NAMES,
    STEP_OF_STAGE,
    duration_text,
)
from ffpfsc_converter.ui.job_presenters import RowStatus


def destination_text(folder: Path | None, home: Path) -> str:
    """Describe la carpeta de descargas, abreviando la carpeta personal con «~».

    Args:
        folder (Path | None): Carpeta elegida, o ``None`` si aún no hay.
        home (Path): Carpeta personal del usuario.

    Returns:
        str: Por ejemplo ``"Descargar en ~/PS5"`` o ``"Sin carpeta de descargas"``.
    """
    if folder is None:
        return "Sin carpeta de descargas"
    try:
        shown = str(Path("~") / folder.relative_to(home))
    except ValueError:
        shown = str(folder)
    return f"Descargar en {shown}"


class TransferProgress(NamedTuple):
    """Avance de una transferencia.

    Attributes:
        percent (float): Porcentaje (0-100).
        text (str): Por ejemplo ``"42% · 20.3 GB de 48.2 GB"``.
    """

    percent: float
    text: str


def transfer_progress(done: int, total: int) -> TransferProgress:
    """Calcula el avance de una transferencia.

    Args:
        done (int): Bytes transferidos.
        total (int): Bytes totales.

    Returns:
        TransferProgress: Porcentaje y texto.
    """
    percent = min(100.0, done * 100 / total) if total else 0.0
    return TransferProgress(percent, f"{percent:.0f}% · {format_size(done)} de "
                                     f"{format_size(total)}")


def download_result_status(result: DownloadResult) -> RowStatus:
    """Resume el resultado de una descarga para su píldora.

    Args:
        result (DownloadResult): Resultado.

    Returns:
        RowStatus: Tipo de píldora, texto y detalle.
    """
    if result.succeeded:
        return RowStatus("ok", "✓ Descargado", f"{result.files} archivo(s) en "
                                               f"{duration_text(result.elapsed_seconds)}")
    if result.cancelled:
        return RowStatus("warn", "Cancelada", "Se puede reanudar")
    first_line = result.message.splitlines()[0] if result.message else "desconocido"
    return RowStatus("bad", "Error", first_line)


def pipeline_step_text(stage: PipelineStage) -> str:
    """Describe el paso de "comprimir y reemplazar" en el que va el juego.

    Args:
        stage (PipelineStage): Etapa interna actual.

    Returns:
        str: Por ejemplo ``"Paso 2 de 3 · Comprimiendo"``.
    """
    step = STEP_OF_STAGE[stage]
    return f"Paso {step + 1} de {len(PIPELINE_STEPS)} · {STAGE_NAMES[stage]}"


def pipeline_progress(percent: float, detail: str) -> TransferProgress:
    """Prepara el avance de la etapa actual para la barra de la fila.

    Args:
        percent (float): Porcentaje de la etapa (se limita a 0-100).
        detail (str): Bytes, velocidad o fase de MkPFS.

    Returns:
        TransferProgress: Porcentaje y texto como ``"62% · 20.3 GB de 48.2 GB"``.
    """
    value = min(max(percent, 0.0), 100.0)
    text = f"{value:.0f}% · {detail}" if detail else f"{value:.0f}%"
    return TransferProgress(value, text)


def pipeline_result_status(result: PipelineResult) -> RowStatus:
    """Resume cómo terminó "comprimir y reemplazar".

    Args:
        result (PipelineResult): Resultado del pipeline.

    Returns:
        RowStatus: Tipo de píldora, texto y detalle (el mensaje del pipeline).
    """
    if result.succeeded:
        return RowStatus("ok", "✓ Reemplazado", result.message)
    if result.cancelled:
        return RowStatus("warn", "Cancelado", result.message)
    return RowStatus("bad", "Error", result.message)
