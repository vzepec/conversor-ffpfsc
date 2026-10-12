"""Análisis en segundo plano de un trabajo recién agregado.

Lee el nombre del juego, mide su tamaño y estima el peso final, publicando un
evento tras cada paso para que la interfaz se actualice progresivamente.
"""
from __future__ import annotations

import threading
from collections.abc import Sequence

from ffpfsc_converter.domain.events import EventSink, JobEstimateReady, JobInfoReady, JobSizeReady
from ffpfsc_converter.domain.lz4 import Lz4Compat
from ffpfsc_converter.domain.models import ConversionJob, FileEntry, SourceKind
from ffpfsc_converter.infrastructure.filesystem import collect_game_files
from ffpfsc_converter.services.ampr_compat import detect_compat
from ffpfsc_converter.services.estimator import estimate_sizes
from ffpfsc_converter.services.lz4_estimator import estimate_lz4
from ffpfsc_converter.services.metadata import read_game_info


def analyze_job(job: ConversionJob, levels: Sequence[int], emit: EventSink) -> None:
    """Completa ``info``, ``size`` y las estimaciones del trabajo (bloqueante).

    Modifica ``job`` a propósito y publica ``JobInfoReady``, ``JobSizeReady`` y
    ``JobEstimateReady`` en ese orden (sin estimación si ya es un ``.ffpfsc``). La
    estimación incluye si admite LZ4 y su peso en ese formato.

    Args:
        job (ConversionJob): Trabajo a analizar.
        levels (Sequence[int]): Niveles de compresión a estimar.
        emit (EventSink): Destino de los eventos.

    Raises:
        OSError: Si la imagen del juego deja de ser accesible durante el análisis.
    """
    job.info = read_game_info(job.game_root)
    emit(JobInfoReady(job))
    files = collect_game_files(job.game_root)
    job.size = sum(f.size for f in files)
    emit(JobSizeReady(job))
    if job.already_compressed:  # un .ffpfsc no se vuelve a comprimir: no hay qué estimar
        return
    estimates = estimate_sizes(files, levels)
    job.estimates, job.performance_estimates = estimates.standard, estimates.performance
    _analyze_lz4(job, files)
    emit(JobEstimateReady(job))


def _analyze_lz4(job: ConversionJob, files: Sequence[FileEntry]) -> None:
    """Completa si el juego admite LZ4 y cuánto pesaría (solo carpetas).

    Modifica ``job`` a propósito.

    Args:
        job (ConversionJob): Trabajo analizado.
        files (Sequence[FileEntry]): Archivos del juego.
    """
    if job.kind is not SourceKind.FOLDER:  # una imagen no se puede revisar por dentro
        job.lz4_compat = Lz4Compat.UNKNOWN
        return
    job.lz4_compat = detect_compat(job.game_root)
    job.lz4_estimate = estimate_lz4(files, job.game_root)


def start_analysis(job: ConversionJob, levels: Sequence[int], emit: EventSink) -> threading.Thread:
    """Ejecuta ``analyze_job`` en un hilo daemon.

    Args:
        job (ConversionJob): Trabajo a analizar.
        levels (Sequence[int]): Niveles de compresión a estimar.
        emit (EventSink): Destino de los eventos (seguro entre hilos).

    Returns:
        threading.Thread: Hilo ya iniciado.
    """
    thread = threading.Thread(target=analyze_job, args=(job, levels, emit), daemon=True)
    thread.start()
    return thread
