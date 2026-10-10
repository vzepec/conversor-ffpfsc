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
    """Modo de compresión ofrecido al usuario.

    Attributes:
        label (str): Texto completo que se muestra en el selector.
        short_label (str): Nombre corto que se usa en el registro.
        level (int): Nivel de compresión zlib (1-9).
    """

    label: str
    short_label: str
    level: int


class SourceKind(Enum):
    """Tipo de origen. El valor coincide con el modo de ``mkpfs pack``."""

    FOLDER = "folder"
    IMAGE = "file"


class JobState(Enum):
    """Estado de un trabajo dentro de la cola de conversión."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class GameInfo:
    """Metadatos del juego leídos de ``sce_sys/param.json``.

    Attributes:
        title (str): Nombre oficial del juego; vacío si no se pudo leer.
        title_id (str): Identificador del título, por ejemplo ``PPSA01234``.
        version (str): Versión del contenido, por ejemplo ``01.000.000``.
    """

    title: str = ""
    title_id: str = ""
    version: str = ""


@dataclass(frozen=True)
class FileEntry:
    """Archivo que forma parte de un juego.

    Attributes:
        path (str): Ruta absoluta del archivo.
        size (int): Tamaño en bytes.
    """

    path: str
    size: int


@dataclass(frozen=True)
class ConversionOptions:
    """Parámetros elegidos por el usuario para una tanda de conversiones.

    Attributes:
        compression_level (int): Nivel de compresión zlib (1-9).
        cpu_count (int): Núcleos que puede usar MkPFS.
        full_verify (bool): ``True`` para verificar cada bloque al terminar.
    """

    compression_level: int
    cpu_count: int
    full_verify: bool


@dataclass(frozen=True)
class ProgressUpdate:
    """Línea de progreso emitida por MkPFS.

    Attributes:
        percent (int): Porcentaje completado de la fase actual (0-100).
        phase (str): Fase de MkPFS (``scan``, ``compress``, ``write``, ``verify``).
        speed (str | None): Velocidad informada, por ejemplo ``512.3 MB/s``.
    """

    percent: int
    phase: str
    speed: str | None = None


@dataclass(frozen=True)
class ConversionResult:
    """Resultado de convertir un trabajo.

    Attributes:
        succeeded (bool): ``True`` si el ``.ffpfsc`` se generó correctamente.
        cancelled (bool): ``True`` si el usuario canceló la conversión.
        elapsed_seconds (float): Duración de la conversión.
        output_size (int): Tamaño del archivo generado; ``0`` si falló.
        message (str): Detalle técnico (código de salida o error).
    """

    succeeded: bool
    cancelled: bool
    elapsed_seconds: float
    output_size: int = 0
    message: str = ""


@dataclass
class ConversionJob:
    """Juego en la cola de conversión.

    Attributes:
        source (Path): Ruta que agregó el usuario.
        game_root (Path): Lo que realmente se empaqueta (carpeta con
            ``eboot.bin`` o imagen encontrada).
        output (Path): Ruta del ``.ffpfsc`` que se generará.
        info (GameInfo): Metadatos del juego, disponibles tras el análisis.
        size (int): Tamaño total del juego en bytes, disponible tras el análisis.
        estimates (dict[int, int]): Peso final estimado por nivel de compresión.
        state (JobState): Estado actual en la cola.
        id (str): Identificador único, usado también como fila de la tabla.
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
        """Indica si el trabajo empaqueta una carpeta o una imagen.

        Returns:
            SourceKind: ``IMAGE`` si ``game_root`` es un archivo; ``FOLDER`` si no.
        """
        return SourceKind.IMAGE if self.game_root.is_file() else SourceKind.FOLDER

    @property
    def is_queued(self) -> bool:
        """Indica si el trabajo sigue pendiente de convertir.

        Returns:
            bool: ``True`` si su estado es ``QUEUED``.
        """
        return self.state is JobState.QUEUED

    def estimate_for(self, level: int) -> int | None:
        """Obtiene el peso final estimado para un nivel de compresión.

        Args:
            level (int): Nivel de compresión zlib.

        Returns:
            int | None: Bytes estimados, o ``None`` si aún no se calculó.
        """
        return self.estimates.get(level)
