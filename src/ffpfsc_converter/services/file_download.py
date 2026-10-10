"""Descarga de un único archivo con reanudación y verificación de tamaño.

El archivo se escribe como ``nombre.part`` y solo se renombra al nombre final
cuando tiene exactamente el tamaño esperado. Si la descarga se corta, el
``.part`` queda y la siguiente vez se continúa desde donde quedó (``REST``),
comprobando antes que la PS5 de verdad envíe desde esa posición.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, cast

from ffpfsc_converter.config import FTP_MAX_RESUME_OFFSET, RESUME_OVERLAP_BYTES
from ffpfsc_converter.domain.remote import FileTransfer
from ffpfsc_converter.errors import ConverterError, DownloadCancelledError, TransientError
from ffpfsc_converter.services.download_planner import partial_path
from ffpfsc_converter.services.progress_meter import ProgressMeter
from ffpfsc_converter.services.remote_client import RemoteClient
from ffpfsc_converter.services.resume_writer import LocalOSError, ResumingWriter


class LocalWriteError(ConverterError):
    """No se pudo escribir en este equipo (por ejemplo, disco lleno)."""

    def __init__(self, path: Path, exc: OSError) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            path (Path): Archivo que no se pudo escribir.
            exc (OSError): Error original del sistema.
        """
        super().__init__(f"No se pudo escribir en este equipo:\n{path}\n\n{exc.strerror or exc}")


class IncompleteDownloadError(TransientError):
    """El archivo descargado no tiene el tamaño que informó la PS5."""

    def __init__(self, transfer: FileTransfer, actual: int) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            transfer (FileTransfer): Archivo afectado.
            actual (int): Bytes realmente recibidos.
        """
        super().__init__(
            f"El archivo {transfer.local_path.name} quedó incompleto "
            f"({actual} de {transfer.size} bytes). Vuelve a descargarlo para continuar."
        )


def download_file(
    client: RemoteClient,
    transfer: FileTransfer,
    meter: ProgressMeter,
    should_cancel: Callable[[], bool],
) -> None:
    """Descarga un archivo, reanudando si existe un ``.part`` previo.

    Si el archivo final ya existe con el tamaño correcto, no se descarga. Al
    reanudar se verifica que la PS5 continúe desde donde quedó (ver
    :mod:`~ffpfsc_converter.services.resume_writer`).

    Args:
        client (RemoteClient): Cliente conectado.
        transfer (FileTransfer): Archivo remoto y su ruta local.
        meter (ProgressMeter): Medidor donde se suma el avance.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Raises:
        DownloadCancelledError: Si se canceló durante la descarga.
        LocalWriteError: Si no se pudo escribir en el disco local.
        IncompleteDownloadError: Si el tamaño final no coincide con el esperado.
        ResumeMismatchError: Si el ``.part`` no coincidía con la PS5 (se borra).
        OversizeDownloadError: Si la PS5 envió más datos de los esperados (se borra).
    """
    final, part = transfer.local_path, partial_path(transfer.local_path)
    if final.is_file() and final.stat().st_size == transfer.size:
        meter.skip(transfer.size)
        return
    offset = part.stat().st_size if part.is_file() else 0
    if offset > transfer.size or offset - RESUME_OVERLAP_BYTES > FTP_MAX_RESUME_OFFSET:
        offset = 0  # la PS5 no puede retomar desde ahí: se descarga de nuevo
    meter.skip(offset)
    overlap = min(offset, RESUME_OVERLAP_BYTES)

    def on_chunk(_size: int) -> None:
        """Aborta la descarga si el usuario canceló (el avance lo suma el escritor).

        Args:
            _size (int): Bytes recibidos.

        Raises:
            DownloadCancelledError: Si se pidió cancelar.
        """
        if should_cancel():
            raise DownloadCancelledError()

    progress = (lambda size: meter.advance(size, final.name), meter.rewind)
    try:
        final.parent.mkdir(parents=True, exist_ok=True)
        writer = ResumingWriter(part, transfer.size, offset, overlap, progress)
    except OSError as exc:
        raise LocalWriteError(part, exc) from exc
    with writer:
        try:
            if offset < transfer.size or transfer.size == 0:
                client.download(transfer.remote_path, cast(BinaryIO, writer),
                                offset - overlap, on_chunk)
                writer.finish()
        except LocalOSError as exc:
            raise LocalWriteError(part, exc.original) from exc.original
    _finalize(transfer, part, final)


def _finalize(transfer: FileTransfer, part: Path, final: Path) -> None:
    """Verifica el tamaño del ``.part`` y lo renombra al nombre definitivo.

    Args:
        transfer (FileTransfer): Archivo descargado.
        part (Path): Archivo temporal.
        final (Path): Ruta definitiva.

    Raises:
        IncompleteDownloadError: Si el tamaño no coincide con el esperado.
        LocalWriteError: Si no se pudo renombrar el archivo.
    """
    actual = part.stat().st_size
    if actual != transfer.size:
        raise IncompleteDownloadError(transfer, actual)
    try:
        os.replace(part, final)
    except OSError as exc:
        raise LocalWriteError(final, exc) from exc
