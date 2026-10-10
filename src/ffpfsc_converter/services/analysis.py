"""Análisis en segundo plano de un trabajo recién agregado.

Lee el nombre del juego, mide su tamaño y estima el peso final, publicando un
evento tras cada paso para que la interfaz se actualice progresivamente.
"""
from __future__ import annotations

import threading
from collections.abc import Sequence

from ffpfsc_converter.domain.events import EventSink, JobEstimateReady, JobInfoReady, JobSizeReady
from ffpfsc_converter.domain.models import ConversionJob
from ffpfsc_converter.infrastructure.filesystem import collect_game_files
from ffpfsc_converter.services.estimator import estimate_sizes
from ffpfsc_converter.services.metadata import read_game_info


def analyze_job(job: ConversionJob, levels: Sequence[int], emit: EventSink) -> None:
    """Completa ``info``, ``size`` y ``estimates`` del trabajo (bloqueante).

    Modifica ``job`` a propósito y publica ``JobInfoReady``, ``JobSizeReady`` y
    ``JobEstimateReady`` en ese orden.

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
    job.estimates = estimate_sizes(files, levels)
    emit(JobEstimateReady(job))


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
