"""Eventos que los servicios publican hacia la interfaz.

Los servicios corren en hilos de fondo y nunca tocan widgets: publican uno de
estos eventos mediante un :data:`EventSink` y la UI los consume en su hilo.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ffpfsc_converter.domain.models import ConversionJob, ConversionResult, ProgressUpdate


@dataclass(frozen=True)
class JobInfoReady:
    job: ConversionJob


@dataclass(frozen=True)
class JobSizeReady:
    job: ConversionJob


@dataclass(frozen=True)
class JobEstimateReady:
    job: ConversionJob


@dataclass(frozen=True)
class JobStarted:
    job: ConversionJob
    command: str


@dataclass(frozen=True)
class JobProgress:
    job: ConversionJob
    progress: ProgressUpdate


@dataclass(frozen=True)
class LogMessage:
    text: str


@dataclass(frozen=True)
class JobFinished:
    job: ConversionJob
    result: ConversionResult


@dataclass(frozen=True)
class QueueFinished:
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
