"""Eventos del pipeline y de las operaciones que modifican la PS5 (borrar, subir)."""
from __future__ import annotations

from dataclasses import dataclass

from ffpfsc_converter.domain.models import ConversionJob
from ffpfsc_converter.domain.pipeline import PipelineResult, PipelineStage, ReplacePlan


@dataclass(frozen=True)
class PipelineStageChanged:
    """El pipeline pasó a otra etapa.

    Attributes:
        stage (PipelineStage): Etapa actual.
        detail (str): Texto adicional (por ejemplo, la ruta afectada).
    """

    stage: PipelineStage
    detail: str = ""


@dataclass(frozen=True)
class PipelineProgress:
    """Avance dentro de la etapa actual.

    Attributes:
        stage (PipelineStage): Etapa a la que pertenece el avance.
        percent (float): Porcentaje de la etapa (0-100).
        detail (str): Texto de progreso (bytes, velocidad, fase de MkPFS…).
        eta_seconds (float | None): Tiempo restante estimado; ``None`` si aún no se sabe.
        can_skip (bool): ``True`` mientras se verifica un LZ4 (se puede saltar).
    """

    stage: PipelineStage
    percent: float
    detail: str
    eta_seconds: float | None = None
    can_skip: bool = False


@dataclass(frozen=True)
class PipelineOptionsRequired:
    """Hay que mostrar la ventana de compresión y esperar la elección.

    Attributes:
        job (ConversionJob): Juego descargado y analizado (con estimaciones).
        plan (ReplacePlan): Qué se reemplazará en la PS5 con un ``.ffpfsc``.
        lz4_plan (ReplacePlan | None): Lo mismo con una carpeta LZ4; ``None`` si el
            original es una imagen.
    """

    job: ConversionJob
    plan: ReplacePlan
    lz4_plan: ReplacePlan | None = None


@dataclass(frozen=True)
class PipelineConfirmRequired:
    """Hay que pedir una confirmación adicional (por ejemplo, borrar antes de subir).

    Attributes:
        message (str): Pregunta para el usuario.
    """

    message: str


@dataclass(frozen=True)
class PipelineFinished:
    """El pipeline terminó.

    Attributes:
        result (PipelineResult): Resultado.
    """

    result: PipelineResult


@dataclass(frozen=True)
class RemoteDeleteProgress:
    """Avance de un borrado en la PS5.

    Attributes:
        path (str): Ruta que se está borrando.
        files_done (int): Elementos borrados.
        files_total (int): Elementos totales (0 mientras se cuentan).
    """

    path: str
    files_done: int
    files_total: int


@dataclass(frozen=True)
class RemoteDeleted:
    """Terminó el borrado de las rutas pedidas.

    Attributes:
        paths (tuple[str, ...]): Rutas borradas.
    """

    paths: tuple[str, ...]


@dataclass(frozen=True)
class UploadProgress:
    """Avance de una subida a la PS5.

    Attributes:
        upload_id (str): Identificador de la fila de la subida.
        name (str): Nombre del archivo.
        done (int): Bytes enviados.
        total (int): Bytes totales.
        bytes_per_second (float): Velocidad reciente.
        eta_seconds (float | None): Tiempo restante estimado; ``None`` si aún no se sabe.
    """

    upload_id: str
    name: str
    done: int
    total: int
    bytes_per_second: float
    eta_seconds: float | None = None


@dataclass(frozen=True)
class UploadFinished:
    """Terminó una subida.

    Attributes:
        upload_id (str): Identificador de la fila de la subida.
        succeeded (bool): ``True`` si quedó verificada en la PS5.
        message (str): Resumen o causa del error.
    """

    upload_id: str
    succeeded: bool
    message: str
