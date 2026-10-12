"""Comprobaciones antes de iniciar la conversión de la cola (con diálogos).

Con LZ4 se omiten los juegos que no sirven (imágenes o sin libSceAmpr) avisando
antes; luego, por cada juego, se confirma reemplazar la salida y el espacio libre.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions, OutputFormat
from ffpfsc_converter.services.lz4_local_files import lz4_output_path
from ffpfsc_converter.services.preflight import check_free_space
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui import job_presenters as jp

NOTHING_FOR_LZ4_TEXT = "Ningún juego de la cola se puede comprimir en LZ4."


def confirm_start(jobs: Sequence[ConversionJob],
                  options: ConversionOptions) -> list[ConversionJob]:
    """Elige los trabajos que se convertirán, preguntando lo necesario.

    Args:
        jobs (Sequence[ConversionJob]): Trabajos pendientes.
        options (ConversionOptions): Opciones elegidas.

    Returns:
        list[ConversionJob]: Trabajos a convertir (vacía si se canceló o no queda ninguno).
    """
    ready = list(jobs)
    if options.output_format is OutputFormat.LZ4:
        ready = _lz4_ready(ready)
    if not all(_confirm_job(job, options) for job in ready):
        return []
    return ready


def planned_output(job: ConversionJob, options: ConversionOptions) -> Path:
    """Calcula dónde quedará el resultado según el formato.

    Args:
        job (ConversionJob): Trabajo.
        options (ConversionOptions): Opciones elegidas.

    Returns:
        Path: ``.ffpfsc`` o carpeta ``-LZ4``.
    """
    return lz4_output_path(job) if options.output_format is OutputFormat.LZ4 else job.output


def _lz4_ready(jobs: list[ConversionJob]) -> list[ConversionJob]:
    """Quita los juegos que no se pueden comprimir en LZ4, avisando cuáles y por qué.

    Args:
        jobs (list[ConversionJob]): Trabajos pendientes.

    Returns:
        list[ConversionJob]: Los que sí se pueden (vacía si el usuario no quiso seguir).
    """
    skipped = [(job, jp.lz4_problem(job)) for job in jobs if jp.lz4_problem(job)]
    ready = [job for job in jobs if not jp.lz4_problem(job)]
    if not skipped:
        return ready
    if not ready:
        dialogs.show_info(NOTHING_FOR_LZ4_TEXT)
        return []
    lines = "\n".join(f"• {job.info.title or job.source.name}: {why}" for job, why in skipped)
    return ready if dialogs.confirm_warning(f"Se omitirán:\n\n{lines}\n\n¿Seguir con el resto?") \
        else []


def _confirm_job(job: ConversionJob, options: ConversionOptions) -> bool:
    """Pide confirmación si se va a reemplazar la salida o si puede faltar espacio.

    Args:
        job (ConversionJob): Trabajo a comprobar.
        options (ConversionOptions): Opciones elegidas.

    Returns:
        bool: ``True`` si se puede convertir el trabajo.
    """
    output = planned_output(job, options)
    if output.exists() and not dialogs.confirm_overwrite(output):
        return False
    space = check_free_space(job, options)
    return space is None or space.is_enough or dialogs.confirm_low_space(space)
