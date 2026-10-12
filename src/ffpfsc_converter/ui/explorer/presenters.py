"""Textos de la vista PS5. Funciones puras, sin tkinter (testeables)."""
from __future__ import annotations

import posixpath
import re

from ffpfsc_converter.domain.pipeline import PipelineStage, ReplacePlan
from ffpfsc_converter.domain.remote import (
    RemoteEntry,
    StorageVolume,
)
from ffpfsc_converter.formatting import format_size

#: Los 3 pasos que ve el usuario en "comprimir y reemplazar".
PIPELINE_STEPS = ("Descarga", "Compresión", "Reemplazo")
#: Paso visible al que pertenece cada etapa interna.
STEP_OF_STAGE = {
    PipelineStage.DOWNLOAD: 0,
    PipelineStage.VERIFY_DOWNLOAD: 0,
    PipelineStage.ANALYZE: 1,
    PipelineStage.COMPRESS: 1,
    PipelineStage.CHECK_SPACE: 2,
    PipelineStage.UPLOAD: 2,
    PipelineStage.VERIFY_UPLOAD: 2,
    PipelineStage.DELETE_ORIGINAL: 2,
    PipelineStage.RENAME: 2,
    PipelineStage.RESTORE_FTP: 2,
    PipelineStage.CLEANUP: 2,
}
#: Descripción de cada etapa interna (se muestra como subpaso).
STAGE_NAMES = {
    PipelineStage.DOWNLOAD: "Descargando de la PS5",
    PipelineStage.VERIFY_DOWNLOAD: "Comprobando la descarga (CRC32)",
    PipelineStage.ANALYZE: "Analizando el juego",
    PipelineStage.COMPRESS: "Comprimiendo",
    PipelineStage.CHECK_SPACE: "Comprobando el espacio de la PS5",
    PipelineStage.UPLOAD: "Subiendo",
    PipelineStage.VERIFY_UPLOAD: "Comprobando la subida (CRC32)",
    PipelineStage.DELETE_ORIGINAL: "Borrando el original en la PS5",
    PipelineStage.RENAME: "Publicando el juego comprimido",
    PipelineStage.RESTORE_FTP: "Volviendo el FTP a solo lectura",
    PipelineStage.CLEANUP: "Borrando archivos temporales",
}


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


def replace_summary(plan: ReplacePlan, is_lz4: bool) -> str:
    """Explica qué pasará en la PS5 al comprimir y reemplazar.

    Args:
        plan (ReplacePlan): Qué se borra y dónde se sube.
        is_lz4 (bool): ``True`` si se reemplaza por una carpeta LZ4.

    Returns:
        str: Líneas con las rutas exactas y el aviso de cerrar el juego.
    """
    if is_lz4:
        lines = [f"La carpeta LZ4 reemplazará a {plan.original.path} cuando se compruebe "
                 "que se subió bien."]
    else:
        lines = [f"Se subirá {plan.remote_final} y, una vez verificado, se BORRARÁ de la "
                 f"PS5: {plan.original.path}"]
        if plan.final_exists:
            lines.append(f"Ya existe {plan.remote_final}: se reemplazará.")
    lines.append("Cierra el juego en la PS5 antes de continuar.")
    return "\n".join(lines)
