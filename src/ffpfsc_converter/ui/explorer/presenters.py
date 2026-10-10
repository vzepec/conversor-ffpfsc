"""Textos de la pestaña PS5. Funciones puras, sin tkinter (testeables)."""
from __future__ import annotations

import posixpath

from ffpfsc_converter.domain.remote import DownloadJob, DownloadResult, RemoteEntry
from ffpfsc_converter.formatting import format_size

FOLDER_ICON = "📁"
FILE_ICON = "📄"


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
