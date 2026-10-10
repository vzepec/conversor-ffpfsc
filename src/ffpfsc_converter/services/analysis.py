"""Análisis en segundo plano de un trabajo recién agregado.

Lee el nombre del juego, mide su tamaño y estima el peso final, publicando un
evento tras cada paso para que la UI se actualice progresivamente.
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
    """Completa ``info``, ``size`` y ``estimates`` del trabajo (bloqueante)."""
    job.info = read_game_info(job.game_root)
    emit(JobInfoReady(job))
    files = collect_game_files(job.game_root)
    job.size = sum(f.size for f in files)
    emit(JobSizeReady(job))
    job.estimates = estimate_sizes(files, levels)
    emit(JobEstimateReady(job))


def start_analysis(job: ConversionJob, levels: Sequence[int], emit: EventSink) -> threading.Thread:
    """Ejecuta :func:`analyze_job` en un hilo daemon."""
    thread = threading.Thread(target=analyze_job, args=(job, levels, emit), daemon=True)
    thread.start()
    return thread
