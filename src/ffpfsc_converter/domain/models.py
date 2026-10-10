"""Modelos de dominio del conversor.

Este módulo no importa nada del resto del paquete ni de librerías de terceros:
es la base sobre la que se construyen las demás capas.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class CompressionPreset:
    """Un modo de compresión ofrecido al usuario."""

    label: str
    short_label: str
    level: int


class SourceKind(Enum):
    """Tipo de origen. El valor coincide con el modo de ``mkpfs pack``."""

    FOLDER = "folder"
    IMAGE = "file"


class JobState(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class GameInfo:
    """Metadatos del juego leídos de ``sce_sys/param.json``."""

    title: str = ""
    title_id: str = ""
    version: str = ""


@dataclass(frozen=True)
class FileEntry:
    path: str
    size: int


@dataclass(frozen=True)
class ConversionOptions:
    """Parámetros elegidos por el usuario para una tanda de conversiones."""

    compression_level: int
    cpu_count: int
    full_verify: bool


@dataclass(frozen=True)
class ProgressUpdate:
    """Una línea de progreso emitida por MkPFS."""

    percent: int
    phase: str
    speed: str | None = None


@dataclass(frozen=True)
class ConversionResult:
    succeeded: bool
    cancelled: bool
    elapsed_seconds: float
    output_size: int = 0
    message: str = ""


@dataclass
class ConversionJob:
    """Un juego en la cola de conversión.

    ``source`` es lo que el usuario agregó; ``game_root`` es lo que realmente
    se empaqueta (la carpeta con ``eboot.bin`` o la imagen encontrada).
    """

    source: Path
    game_root: Path
    output: Path
    info: GameInfo = field(default_factory=GameInfo)
    size: int = 0
    estimates: dict[int, int] = field(default_factory=dict)
    state: JobState = JobState.QUEUED
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def kind(self) -> SourceKind:
        return SourceKind.IMAGE if self.game_root.is_file() else SourceKind.FOLDER

    @property
    def is_queued(self) -> bool:
        return self.state is JobState.QUEUED

    def estimate_for(self, level: int) -> int | None:
        return self.estimates.get(level)
