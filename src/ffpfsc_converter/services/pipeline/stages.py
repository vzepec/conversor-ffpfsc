"""Etapas locales del pipeline: descargar, preparar, comprimir y limpiar."""
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
from ffpfsc_converter.services.discovery import create_job
from ffpfsc_converter.services.pipeline.compress import Compressor
from ffpfsc_converter.services.pipeline.reporter import PipelineReporter
from ffpfsc_converter.services.preflight import check_free_space
from ffpfsc_converter.services.remote_client import ClientFactory
from ffpfsc_converter.services.remote_download import NotEnoughSpaceError, download_with_retries


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


def prepare_stage(local: Path, work_dir: Path, reporter: PipelineReporter) -> ConversionJob:
    """Crea y analiza el trabajo de conversión (nombre, tamaño y estimaciones).

    Args:
        local (Path): Carpeta o imagen descargada.
        work_dir (Path): Carpeta local de trabajo (destino del ``.ffpfsc``).
        reporter (PipelineReporter): Publica la etapa.

    Returns:
        ConversionJob: Trabajo analizado.
    """
    reporter.stage(PipelineStage.ANALYZE, local.name)
    job = create_job(local, work_dir)
    analyze_job(job, sorted({p.level for p in PRESETS}), lambda _e: None)
    return job


def compress_stage(job: ConversionJob, choice: PipelineChoice, compressor: Compressor,
                   reporter: PipelineReporter, should_cancel: Callable[[], bool]) -> None:
    """Comprime el juego tras comprobar el espacio local.

    Args:
        job (ConversionJob): Trabajo analizado.
        choice (PipelineChoice): Opciones elegidas.
        compressor (Compressor): Función de compresión.
        reporter (PipelineReporter): Publica etapa y progreso.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Raises:
        NotEnoughSpaceError: Si no cabe el ``.ffpfsc`` en este equipo.
        DownloadCancelledError: Si se canceló.
        ConverterError: Si MkPFS falla.
    """
    space = check_free_space(job, choice.options.compression_level)
    if space is not None and not space.is_enough:
        raise NotEnoughSpaceError(space.needed, free_space(job.output.parent))
    reporter.stage(PipelineStage.COMPRESS, job.output.name)
    result = compressor(job, choice.options, reporter.on_compress, should_cancel)
    if result.cancelled or should_cancel():
        raise DownloadCancelledError()
    if not result.succeeded:
        raise ConverterError(f"MkPFS no pudo comprimir el juego ({result.message}).")


def cleanup_stage(job: ConversionJob, work_dir: Path, reporter: PipelineReporter) -> None:
    """Borra la descarga y el ``.ffpfsc`` locales (solo tras un reemplazo exitoso).

    Args:
        job (ConversionJob): Trabajo cuyo origen y salida se borran.
        work_dir (Path): Carpeta de trabajo (se borra si queda vacía).
        reporter (PipelineReporter): Publica la etapa.
    """
    reporter.stage(PipelineStage.CLEANUP, str(work_dir))
    remove_path(job.source)
    remove_path(job.output)
    with contextlib.suppress(OSError):
        work_dir.rmdir()  # solo si quedó vacía
