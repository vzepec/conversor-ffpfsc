"""Descarga de un único archivo con reanudación y verificación de tamaño.

El archivo se escribe como ``nombre.part`` y solo se renombra al nombre final
cuando tiene exactamente el tamaño esperado. Si la descarga se corta, el
``.part`` queda y la siguiente vez se continúa desde donde quedó (``REST``).
"""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, cast

from ffpfsc_converter.domain.remote import FileTransfer
from ffpfsc_converter.errors import ConverterError, DownloadCancelledError, TransientError
from ffpfsc_converter.services.download_planner import partial_path
from ffpfsc_converter.services.progress_meter import ProgressMeter
from ffpfsc_converter.services.remote_client import RemoteClient


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

    Si el archivo final ya existe con el tamaño correcto, no se descarga.

    Args:
        client (RemoteClient): Cliente conectado.
        transfer (FileTransfer): Archivo remoto y su ruta local.
        meter (ProgressMeter): Medidor donde se suma el avance.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Raises:
        DownloadCancelledError: Si se canceló durante la descarga.
        LocalWriteError: Si no se pudo escribir en el disco local.
        IncompleteDownloadError: Si el tamaño final no coincide con el esperado.
    """
    final, part = transfer.local_path, partial_path(transfer.local_path)
    if final.is_file() and final.stat().st_size == transfer.size:
        meter.skip(transfer.size)
        return
    offset = part.stat().st_size if part.is_file() else 0
    if offset > transfer.size:
        offset = 0
    meter.skip(offset)
    name = final.name

    def on_chunk(size: int) -> None:
        """Suma el bloque recibido y aborta si el usuario canceló.

        Args:
            size (int): Bytes recibidos.

        Raises:
            DownloadCancelledError: Si se pidió cancelar.
        """
        if should_cancel():
            raise DownloadCancelledError()
        meter.advance(size, name)

    try:
        final.parent.mkdir(parents=True, exist_ok=True)
        sink = part.open("ab" if offset else "wb")
    except OSError as exc:
        raise LocalWriteError(part, exc) from exc
    with sink:
        try:
            if offset < transfer.size or transfer.size == 0:
                client.download(transfer.remote_path, cast(BinaryIO, _GuardedSink(sink)),
                                offset, on_chunk)
        except _LocalOSError as exc:
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


class _LocalOSError(Exception):
    """Envoltorio para distinguir errores del disco local de los de red."""

    def __init__(self, original: OSError) -> None:
        """Guarda el error original.

        Args:
            original (OSError): Error del sistema al escribir.
        """
        super().__init__(str(original))
        self.original = original


class _GuardedSink:
    """Archivo de destino que marca sus errores como locales."""

    def __init__(self, sink: BinaryIO) -> None:
        """Envuelve un archivo abierto.

        Args:
            sink (BinaryIO): Archivo binario abierto para escritura.
        """
        self._sink = sink

    def write(self, data: bytes) -> int:
        """Escribe datos en el archivo local.

        Args:
            data (bytes): Datos recibidos.

        Returns:
            int: Bytes escritos.

        Raises:
            _LocalOSError: Si el sistema rechaza la escritura.
        """
        try:
            return self._sink.write(data)
        except OSError as exc:
            raise _LocalOSError(exc) from exc
