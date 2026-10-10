"""Eventos que los servicios publican hacia la interfaz.

Los servicios corren en hilos de fondo y nunca tocan widgets: publican uno de
estos eventos mediante un :data:`EventSink` y la interfaz los consume en su hilo.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ffpfsc_converter.domain.models import ConversionJob, ConversionResult, ProgressUpdate


@dataclass(frozen=True)
class JobInfoReady:
    """Los metadatos del juego (``job.info``) ya están disponibles.

    Attributes:
        job (ConversionJob): Trabajo actualizado.
    """

    job: ConversionJob


@dataclass(frozen=True)
class JobSizeReady:
    """El tamaño total del juego (``job.size``) ya está calculado.

    Attributes:
        job (ConversionJob): Trabajo actualizado.
    """

    job: ConversionJob


@dataclass(frozen=True)
class JobEstimateReady:
    """Las estimaciones de peso final (``job.estimates``) ya están calculadas.

    Attributes:
        job (ConversionJob): Trabajo actualizado.
    """

    job: ConversionJob


@dataclass(frozen=True)
class JobStarted:
    """Comenzó la conversión de un trabajo.

    Attributes:
        job (ConversionJob): Trabajo que se está convirtiendo.
        command (str): Comando de MkPFS ejecutado, para el registro.
    """

    job: ConversionJob
    command: str


@dataclass(frozen=True)
class JobProgress:
    """MkPFS informó un avance.

    Attributes:
        job (ConversionJob): Trabajo en curso.
        progress (ProgressUpdate): Fase, porcentaje y velocidad.
        eta_seconds (float | None): Tiempo restante estimado de la fase; ``None`` si aún
            no se sabe.
    """

    job: ConversionJob
    progress: ProgressUpdate
    eta_seconds: float | None = None


@dataclass(frozen=True)
class LogMessage:
    """Línea de texto para el registro.

    Attributes:
        text (str): Contenido de la línea.
    """

    text: str


@dataclass(frozen=True)
class JobFinished:
    """Terminó la conversión de un trabajo (con éxito, error o cancelación).

    Attributes:
        job (ConversionJob): Trabajo terminado.
        result (ConversionResult): Resultado de la conversión.
    """

    job: ConversionJob
    result: ConversionResult


@dataclass(frozen=True)
class QueueFinished:
    """Terminó toda la cola de conversión.

    Attributes:
        cancelled (bool): ``True`` si terminó por una cancelación del usuario.
    """

    cancelled: bool


Event = (
    JobInfoReady
    | JobSizeReady
    | JobEstimateReady
    | JobStarted
    | JobProgress
    | LogMessage
    | JobFinished
    | QueueFinished
)

#: Función que recibe eventos. Debe ser segura para llamarse desde cualquier hilo.
EventSink = Callable[[Event], None]
