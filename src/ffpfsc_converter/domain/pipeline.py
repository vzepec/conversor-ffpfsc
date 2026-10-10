"""Modelos del pipeline "comprimir y reemplazar en la PS5"."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions
from ffpfsc_converter.domain.remote import RemoteEntry


class PipelineStage(Enum):
    """Etapas del pipeline, en orden."""

    DOWNLOAD = "download"
    VERIFY_DOWNLOAD = "verify_download"
    ANALYZE = "analyze"
    COMPRESS = "compress"
    CHECK_SPACE = "check_space"
    UPLOAD = "upload"
    VERIFY_UPLOAD = "verify_upload"
    DELETE_ORIGINAL = "delete_original"
    RENAME = "rename"
    RESTORE_FTP = "restore_ftp"
    CLEANUP = "cleanup"


class SpaceStrategy(Enum):
    """Cómo reemplazar según el espacio libre de la PS5."""

    UPLOAD_FIRST = "upload_first"
    DELETE_FIRST = "delete_first"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class ReplacePlan:
    """Qué se borra y dónde se sube en la PS5.

    Attributes:
        original (RemoteEntry): Carpeta o imagen original que se reemplaza.
        remote_final (str): Ruta definitiva del ``.ffpfsc`` en la PS5.
        remote_part (str): Ruta temporal durante la subida (``.ffpfsc.part``).
        final_exists (bool): ``True`` si ya hay un archivo con el nombre definitivo.
    """

    original: RemoteEntry
    remote_final: str
    remote_part: str
    final_exists: bool


@dataclass(frozen=True)
class PipelineChoice:
    """Lo que el usuario eligió en la ventana de compresión.

    Attributes:
        options (ConversionOptions): Nivel, núcleos y verificación.
        delete_local (bool): ``True`` para borrar los archivos temporales al terminar bien.
    """

    options: ConversionOptions
    delete_local: bool


@dataclass(frozen=True)
class PipelineResult:
    """Resultado del pipeline.

    Attributes:
        succeeded (bool): ``True`` si el juego quedó reemplazado en la PS5.
        cancelled (bool): ``True`` si el usuario lo canceló.
        message (str): Resumen o causa del error.
        original_size (int): Tamaño del original en la PS5.
        final_size (int): Tamaño del ``.ffpfsc`` subido.
    """

    succeeded: bool
    cancelled: bool
    message: str
    original_size: int = 0
    final_size: int = 0


@dataclass
class PipelineAttempt:
    """Lo que ya se hizo en un intento, para que un reintento no lo repita.

    Attributes:
        entry (RemoteEntry): Carpeta o imagen de la PS5 a reemplazar.
        siblings (tuple[str, ...]): Nombres de su carpeta remota.
        work_dir (Path): Carpeta local de trabajo.
        original_size (int): Tamaño del original (se conoce tras descargarlo).
        job (ConversionJob | None): Juego ya comprimido; ``None`` si falta comprimir.
        choice (PipelineChoice | None): Opciones elegidas en la ventana de compresión.
        original_deleted (bool): ``True`` si el original ya se borró en la PS5.
    """

    entry: RemoteEntry
    siblings: tuple[str, ...]
    work_dir: Path
    original_size: int = 0
    job: ConversionJob | None = None
    choice: PipelineChoice | None = None
    original_deleted: bool = False
