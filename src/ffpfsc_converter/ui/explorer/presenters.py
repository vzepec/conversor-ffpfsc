"""Textos de la pestaña PS5. Funciones puras, sin tkinter (testeables)."""
from __future__ import annotations

import posixpath
import re
from collections.abc import Iterable

from ffpfsc_converter.domain.pipeline import PipelineStage
from ffpfsc_converter.domain.remote import (
    DownloadJob,
    DownloadResult,
    RemoteEntry,
    StorageVolume,
)
from ffpfsc_converter.formatting import format_size

FOLDER_ICON = "📁"
FILE_ICON = "📄"
UPLOAD_ICON = "⬆"
#: Los 3 pasos que ve el usuario en "comprimir y reemplazar".
PIPELINE_STEPS = ("Descarga", "Compresión", "Reemplazo")
#: Paso visible al que pertenece cada etapa interna.
STEP_OF_STAGE = {
    PipelineStage.DOWNLOAD: 0,
    PipelineStage.ANALYZE: 1,
    PipelineStage.COMPRESS: 1,
    PipelineStage.CHECK_SPACE: 2,
    PipelineStage.UPLOAD: 2,
    PipelineStage.DELETE_ORIGINAL: 2,
    PipelineStage.RENAME: 2,
    PipelineStage.RESTORE_FTP: 2,
    PipelineStage.CLEANUP: 2,
}
#: Descripción de cada etapa interna (se muestra como subpaso).
STAGE_NAMES = {
    PipelineStage.DOWNLOAD: "Descargando de la PS5",
    PipelineStage.ANALYZE: "Analizando el juego",
    PipelineStage.COMPRESS: "Comprimiendo a .ffpfsc",
    PipelineStage.CHECK_SPACE: "Comprobando el espacio de la PS5",
    PipelineStage.UPLOAD: "Subiendo y verificando",
    PipelineStage.DELETE_ORIGINAL: "Borrando el original en la PS5",
    PipelineStage.RENAME: "Publicando el .ffpfsc",
    PipelineStage.RESTORE_FTP: "Volviendo el FTP a solo lectura",
    PipelineStage.CLEANUP: "Borrando archivos temporales",
}


def entry_label(entry: RemoteEntry) -> str:
    """Genera el nombre con icono que se muestra en el explorador.

    Args:
        entry (RemoteEntry): Elemento remoto.

    Returns:
        str: Por ejemplo ``"📁 homebrew"``.
    """
    return f"{FOLDER_ICON if entry.is_dir else FILE_ICON} {entry.name}"


def entry_size_text(entry: RemoteEntry) -> str:
    """Formatea el tamaño de un elemento remoto.

    Args:
        entry (RemoteEntry): Elemento remoto.

    Returns:
        str: Tamaño legible, o vacío en carpetas (su tamaño se conoce al descargar).
    """
    return "" if entry.is_dir else format_size(entry.size)


def modified_text(stamp: str) -> str:
    """Convierte una fecha ``AAAAMMDDhhmmss`` en ``AAAA-MM-DD hh:mm``.

    Args:
        stamp (str): Fecha tal como la envía el servidor.

    Returns:
        str: Fecha legible, o vacío si no es válida.
    """
    if len(stamp) < 12 or not stamp[:12].isdigit():
        return ""
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[8:10]}:{stamp[10:12]}"


def parent_path(path: str) -> str:
    """Calcula la carpeta superior de una ruta remota.

    Args:
        path (str): Ruta absoluta POSIX.

    Returns:
        str: Carpeta superior; ``"/"`` para la raíz.
    """
    return posixpath.dirname(path.rstrip("/")) or "/"


def speed_text(bytes_per_second: float) -> str:
    """Formatea una velocidad de transferencia.

    Args:
        bytes_per_second (float): Velocidad.

    Returns:
        str: Por ejemplo ``"45.2 MB/s"``, o vacío si es cero.
    """
    return f"{format_size(bytes_per_second)}/s" if bytes_per_second > 0 else ""


def progress_text(job: DownloadJob) -> str:
    """Formatea el avance de una descarga.

    Args:
        job (DownloadJob): Descarga en curso.

    Returns:
        str: Por ejemplo ``"42%  (1.2 GB de 2.9 GB)"``.
    """
    if not job.total_bytes:
        return "0%"
    percent = min(100, job.done_bytes * 100 // job.total_bytes)
    return f"{percent}%  ({format_size(job.done_bytes)} de {format_size(job.total_bytes)})"


def download_result_text(result: DownloadResult) -> str:
    """Formatea el resultado final de una descarga.

    Args:
        result (DownloadResult): Resultado.

    Returns:
        str: Archivos y duración si tuvo éxito; motivo si no.
    """
    if result.succeeded:
        return f"✔ {result.files} archivo(s) en {duration_text(result.elapsed_seconds)}"
    if result.cancelled:
        return "✖ Cancelada (se puede reanudar)"
    return f"✖ Error: {result.message.splitlines()[0] if result.message else 'desconocido'}"


def duration_text(seconds: float) -> str:
    """Formatea una duración en segundos o minutos.

    Args:
        seconds (float): Duración.

    Returns:
        str: Por ejemplo ``"12 s"`` o ``"3.5 min"``.
    """
    return f"{seconds:.0f} s" if seconds < 60 else f"{seconds / 60:.1f} min"


def connection_text(host: str, port: int, path: str) -> str:
    """Genera el texto de estado de una conexión activa.

    Args:
        host (str): Dirección de la PS5.
        port (int): Puerto FTP.
        path (str): Carpeta abierta.

    Returns:
        str: Por ejemplo ``"Conectado a 192.168.1.13:2122 — /data/homebrew"``.
    """
    return f"Conectado a {host}:{port} — {path}"


def upload_progress_text(done: int, total: int) -> str:
    """Formatea el avance de una subida.

    Args:
        done (int): Bytes enviados.
        total (int): Bytes totales.

    Returns:
        str: Por ejemplo ``"42%  (1.2 GB de 2.9 GB)"``.
    """
    percent = min(100, done * 100 // total) if total else 100
    return f"{percent}%  ({format_size(done)} de {format_size(total)})"


def delete_summary(paths: list[str], limit: int = 8) -> str:
    """Lista las rutas que se van a borrar (recortando si son muchas).

    Args:
        paths (list[str]): Rutas remotas.
        limit (int): Máximo de rutas a mostrar.

    Returns:
        str: Una ruta por línea, con "… y N más" si se recortó.
    """
    shown = "\n".join(paths[:limit])
    return shown + (f"\n… y {len(paths) - limit} más" if len(paths) > limit else "")


_SLOT = re.compile(r"/mnt/(usb|ext)(\d+)")
_INTERNAL_PATH = "/data"
_NVME_PREFIX = "/dev/nvme"  # M.2; un USB ampliado se monta desde /dev/da*


def volume_name(volume: StorageVolume) -> str:
    """Nombra una unidad de la PS5 como la ve el usuario.

    Args:
        volume (StorageVolume): Unidad montada.

    Returns:
        str: ``"Interno"``, ``"USB 1"``, ``"M.2"``, ``"USB ampliado"``… (numerados desde 1
        cuando hay más de una ranura del mismo tipo).
    """
    if volume.path == _INTERNAL_PATH:
        return "Interno"
    match = _SLOT.fullmatch(volume.path)
    if match is None:
        return volume.path
    kind, index = match.group(1), int(match.group(2))
    if kind == "usb":
        return f"USB {index + 1}"
    name = "M.2" if volume.device.startswith(_NVME_PREFIX) else "USB ampliado"
    return name if index == 0 else f"{name} {index + 1}"


def storage_text(volumes: Iterable[StorageVolume], error: str = "") -> str:
    """Resume el espacio libre de cada unidad en una línea.

    Args:
        volumes (Iterable[StorageVolume]): Unidades montadas.
        error (str): Motivo por el que no se pudo consultar, si falló.

    Returns:
        str: Por ejemplo ``"Espacio libre: Interno 412.3 GB de 825.0 GB · USB 1 58.1 GB
        de 64.0 GB"``; con el interno primero y luego las ranuras en orden.
    """
    if error:
        return f"Espacio libre: {error}."
    ordered = sorted(volumes, key=lambda v: (v.path != _INTERNAL_PATH, v.path))
    if not ordered:
        return "Espacio libre: sin unidades."
    parts = (f"{volume_name(v)} {format_size(v.free_bytes)} de {format_size(v.total_bytes)}"
             for v in ordered)
    return "Espacio libre: " + " · ".join(parts)
