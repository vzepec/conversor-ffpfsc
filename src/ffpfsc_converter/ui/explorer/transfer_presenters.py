"""Textos del panel de transferencias de la vista PS5. Funciones puras."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from ffpfsc_converter.domain.remote import DownloadResult
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.ui.explorer.presenters import duration_text
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
