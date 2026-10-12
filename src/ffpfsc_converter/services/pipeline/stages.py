"""Etapas locales del pipeline: descargar, comprobar, preparar, comprimir y limpiar."""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path

from ffpfsc_converter.config import PRESETS
from ffpfsc_converter.domain.models import ConversionJob
from ffpfsc_converter.domain.pipeline import PipelineChoice, PipelineStage
from ffpfsc_converter.domain.remote import ConsoleTarget, DownloadJob, RemoteEntry
from ffpfsc_converter.errors import ConverterError, DownloadCancelledError
from ffpfsc_converter.infrastructure.filesystem import free_space, remove_path
from ffpfsc_converter.services.analysis import analyze_job
from ffpfsc_converter.services.console_access import ConsoleAccess
from ffpfsc_converter.services.discovery import create_job
from ffpfsc_converter.services.integrity import FilePair, IntegrityError, verify_files
from ffpfsc_converter.services.lz4_local_files import planned_output
from ffpfsc_converter.services.pipeline.compress import CompressControl, Compressor
from ffpfsc_converter.services.pipeline.reporter import PipelineReporter
from ffpfsc_converter.services.preflight import check_free_space
from ffpfsc_converter.services.remote_client import ClientFactory
from ffpfsc_converter.services.remote_download import NotEnoughSpaceError, download_with_retries
from ffpfsc_converter.services.remote_games import ALREADY_LZ4_TEXT, is_lz4_folder


def ensure_not_lz4(factory: ClientFactory, target: ConsoleTarget, entry: RemoteEntry) -> None:
    """Comprueba que una carpeta no esté ya comprimida en LZ4 antes de descargarla.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP de solo lectura.
        entry (RemoteEntry): Elemento a reemplazar.

    Raises:
        ConverterError: Si la carpeta ya está en LZ4 (no tiene sentido volver a comprimirla).
        OSError: Si falla el listado.
    """
    if not entry.is_dir:
        return
    client = factory(target)
    try:
        client.connect()
        if is_lz4_folder(client, entry.path):
            raise ConverterError(ALREADY_LZ4_TEXT)
    finally:
        client.close()


def download_stage(factory: ClientFactory, target: ConsoleTarget, entry: RemoteEntry,
                   work_dir: Path, reporter: PipelineReporter,
                   should_cancel: Callable[[], bool]) -> DownloadJob:
    """Descarga el elemento, reanudando y reintentando tras cortes de conexión.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP de solo lectura.
        entry (RemoteEntry): Elemento remoto.
        work_dir (Path): Carpeta local de trabajo.
        reporter (PipelineReporter): Publica etapa, progreso y reintentos.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Returns:
        DownloadJob: Descarga completada.
    """
    reporter.stage(PipelineStage.DOWNLOAD, entry.path)
    job = DownloadJob(entry, work_dir)
    download_with_retries(factory, target, job, reporter.on_download, should_cancel)
    return job


def verify_download_stage(access: ConsoleAccess, host: str, download: DownloadJob,
                          reporter: PipelineReporter, should_cancel: Callable[[], bool]) -> None:
    """Comprueba con CRC32 que cada archivo descargado es idéntico al de la PS5.

    Si alguno difiere, se borra su copia local para que el reintento lo vuelva a
    descargar.

    Args:
        access (ConsoleAccess): Acceso AVA1 a la consola.
        host (str): Dirección de la PS5.
        download (DownloadJob): Descarga terminada (con su lista de archivos).
        reporter (PipelineReporter): Publica etapa y progreso.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Raises:
        IntegrityError: Si algún archivo no coincide.
        DownloadCancelledError: Si se canceló.
    """
    pairs = [FilePair(f.local_path, f.remote_path, f.size) for f in download.files if f.size]
    reporter.stage(PipelineStage.VERIFY_DOWNLOAD, download.entry.name)
    if not pairs:
        return
    session = access.open_session(host)
    try:
        bad = verify_files(session, pairs, lambda done, total: reporter.report(done, total, 0.0),
                           should_cancel)
    finally:
        session.close()
    for pair in bad:
        with contextlib.suppress(OSError):
            pair.local.unlink()
    if bad:
        raise IntegrityError([pair.local.name for pair in bad], "la descarga")


def prepare_stage(local: Path, work_dir: Path, reporter: PipelineReporter) -> ConversionJob:
    """Crea y analiza el trabajo de conversión (nombre, tamaño y estimaciones).

    Args:
        local (Path): Carpeta o imagen descargada.
        work_dir (Path): Carpeta local de trabajo (destino del juego comprimido).
        reporter (PipelineReporter): Publica la etapa.

    Returns:
        ConversionJob: Trabajo analizado.
    """
    reporter.stage(PipelineStage.ANALYZE, local.name)
    job = create_job(local, work_dir)
    analyze_job(job, sorted({p.level for p in PRESETS}), lambda _e: None)
    return job


def compress_stage(job: ConversionJob, choice: PipelineChoice, compressor: Compressor,
                   reporter: PipelineReporter, control: CompressControl) -> None:
    """Comprime el juego tras comprobar el espacio local.

    Args:
        job (ConversionJob): Trabajo analizado.
        choice (PipelineChoice): Opciones elegidas.
        compressor (Compressor): Función de compresión.
        reporter (PipelineReporter): Publica etapa y progreso.
        control (CompressControl): Cancelación y pedido de saltar la verificación LZ4.

    Raises:
        NotEnoughSpaceError: Si no cabe el juego comprimido en este equipo.
        DownloadCancelledError: Si se canceló.
        ConverterError: Si la compresión falla.
    """
    space = check_free_space(job, choice.options)
    if space is not None and not space.is_enough:
        raise NotEnoughSpaceError(space.needed, free_space(job.output.parent))
    reporter.stage(PipelineStage.COMPRESS, planned_output(job, choice.options).name)
    result = compressor(job, choice.options, reporter.on_compress, control)
    if result.cancelled or control.should_cancel():
        raise DownloadCancelledError()
    if not result.succeeded:
        raise ConverterError(f"No se pudo comprimir el juego ({result.message}).")


def cleanup_stage(job: ConversionJob, output: Path, work_dir: Path,
                  reporter: PipelineReporter) -> None:
    """Borra la descarga y el juego comprimido locales (solo tras un reemplazo exitoso).

    Args:
        job (ConversionJob): Trabajo cuyo origen se borra.
        output (Path): ``.ffpfsc`` o carpeta LZ4 local.
        work_dir (Path): Carpeta de trabajo (se borra si queda vacía).
        reporter (PipelineReporter): Publica la etapa.
    """
    reporter.stage(PipelineStage.CLEANUP, str(work_dir))
    remove_path(job.source)
    remove_path(output)
    with contextlib.suppress(OSError):
        work_dir.rmdir()  # solo si quedó vacía
