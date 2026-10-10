"""Comprueba con CRC32 que archivos de este equipo y de la PS5 son idénticos.

El tamaño igual no basta: un archivo puede medir lo mismo y tener otro
contenido. La PS5 calcula su CRC32 con el helper (``job.run`` CRC32) mientras
este equipo calcula el suyo, en paralelo; el avance combina los dos.
"""
from __future__ import annotations

import time
import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ffpfsc_converter.config import CRC_CHUNK_BYTES, CRC_POLL_SECONDS
from ffpfsc_converter.errors import ConverterError, DownloadCancelledError
from ffpfsc_converter.infrastructure.ava1.jobs import (
    JOB_OP_CRC32,
    JobStatus,
    cancel_job,
    check_done,
    crc32_result,
    is_running,
    job_status,
    start_job,
)
from ffpfsc_converter.infrastructure.ava1.session import Ava1Session

#: Recibe ``(bytes_comprobados, bytes_totales)``; cada archivo cuenta dos veces (local y PS5).
VerifyProgress = Callable[[int, int], None]


class IntegrityError(ConverterError):
    """Un archivo de este equipo no es idéntico al de la PS5."""

    def __init__(self, names: Sequence[str], what: str) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            names (Sequence[str]): Archivos que no coinciden.
            what (str): Qué se estaba comprobando (``"la descarga"``, ``"la subida"``).
        """
        shown = ", ".join(names[:3]) + (f" y {len(names) - 3} más" if len(names) > 3 else "")
        super().__init__(f"La comprobación de {what} falló: {shown} no coincide con la PS5 "
                         "(CRC32 distinto). Al reintentar se volverá a transferir.")


@dataclass(frozen=True)
class FilePair:
    """Archivo local y su equivalente en la PS5.

    Attributes:
        local (Path): Archivo de este equipo.
        remote (str): Ruta absoluta en la PS5.
        size (int): Tamaño esperado en bytes.
    """

    local: Path
    remote: str
    size: int


@dataclass
class _Tracker:
    """Avance de una comparación en curso.

    Attributes:
        remote (JobStatus): Último estado conocido de la tarea de la PS5.
        polled (float): Momento de la última consulta (reloj monotónico).
        local (int): Bytes locales ya leídos.
    """

    remote: JobStatus
    polled: float
    local: int = 0


def local_crc32(path: Path, on_bytes: Callable[[int], None],
                should_cancel: Callable[[], bool]) -> int:
    """Calcula el CRC32 de un archivo local por bloques.

    Args:
        path (Path): Archivo.
        on_bytes (Callable[[int], None]): Recibe el tamaño de cada bloque leído.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Returns:
        int: CRC32 (el mismo que ``zlib.crc32`` de todo el archivo).

    Raises:
        DownloadCancelledError: Si se canceló.
        OSError: Si no se pudo leer el archivo.
    """
    crc = 0
    with path.open("rb") as source:
        while chunk := source.read(CRC_CHUNK_BYTES):
            if should_cancel():
                raise DownloadCancelledError()
            crc = zlib.crc32(chunk, crc)
            on_bytes(len(chunk))
    return crc


def verify_files(session: Ava1Session, pairs: Sequence[FilePair], report: VerifyProgress,
                 should_cancel: Callable[[], bool]) -> list[FilePair]:
    """Compara el CRC32 de cada par y devuelve los que no coinciden.

    Args:
        session (Ava1Session): Sesión emparejada con la PS5.
        pairs (Sequence[FilePair]): Archivos a comparar.
        report (VerifyProgress): Recibe el avance combinado.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Returns:
        list[FilePair]: Pares cuyo contenido difiere.

    Raises:
        DownloadCancelledError: Si se canceló.
        Ava1Refused: Si la PS5 no pudo leer un archivo.
        OSError: Si falla la comunicación o la lectura local.
    """
    total, base = 2 * sum(p.size for p in pairs), 0
    mismatched = []
    for pair in pairs:
        crc_local, crc_remote = _compare_one(session, pair, base, total, report, should_cancel)
        if crc_local != crc_remote:
            mismatched.append(pair)
        base += 2 * pair.size
        report(base, total)
    return mismatched


def _compare_one(session: Ava1Session, pair: FilePair, base: int, total: int,
                 report: VerifyProgress, should_cancel: Callable[[], bool]) -> tuple[int, int]:
    """Calcula en paralelo el CRC32 local y el de la PS5 de un archivo.

    Args:
        session (Ava1Session): Sesión emparejada.
        pair (FilePair): Archivo a comparar.
        base (int): Bytes ya comprobados de archivos anteriores.
        total (int): Bytes totales de la comprobación.
        report (VerifyProgress): Recibe el avance combinado.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Returns:
        tuple[int, int]: CRC32 local y CRC32 de la PS5.

    Raises:
        DownloadCancelledError: Si se canceló (la tarea de la PS5 también se cancela).
        Ava1Refused: Si la PS5 no pudo leer el archivo.
    """
    job = start_job(session, JOB_OP_CRC32, pair.remote)
    tracker = _Tracker(remote=job.status, polled=time.monotonic())

    def tick(size: int) -> None:
        """Suma el bloque local y, cada cierto tiempo, consulta el avance de la PS5.

        Args:
            size (int): Bytes leídos.
        """
        tracker.local += size
        if is_running(tracker.remote) and time.monotonic() - tracker.polled >= CRC_POLL_SECONDS:
            tracker.remote, tracker.polled = job_status(session, job.job_id), time.monotonic()
        report(base + tracker.local + tracker.remote.bytes_done, total)

    try:
        crc_local = local_crc32(pair.local, tick, should_cancel)
    except DownloadCancelledError:
        cancel_job(session, job.job_id)
        raise
    status = tracker.remote
    while is_running(status):
        if should_cancel():
            cancel_job(session, job.job_id)
            raise DownloadCancelledError()
        time.sleep(CRC_POLL_SECONDS)
        status = job_status(session, job.job_id)
        report(base + pair.size + status.bytes_done, total)
    return crc_local, crc32_result(check_done(status))
