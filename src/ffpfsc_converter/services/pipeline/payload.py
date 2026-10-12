"""Lo que se sube al reemplazar: un ``.ffpfsc`` (archivo) o una carpeta LZ4.

Ambos siguen los mismos pasos (subir a la ruta temporal, verificar con CRC32 y
publicar con el nombre definitivo); este módulo elige cómo hacer cada uno según
si la salida local es un archivo o una carpeta.
"""
from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.domain.pipeline import ReplacePlan
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.infrastructure.ftp import join_remote
from ffpfsc_converter.services.integrity import FilePair
from ffpfsc_converter.services.remote_client import ClientFactory
from ffpfsc_converter.services.remote_folder_files import UploadHooks, folder_files
from ffpfsc_converter.services.remote_folder_upload import (
    remote_exists,
    rename_remote,
    upload_folder_to,
)
from ffpfsc_converter.services.remote_upload import publish_with_retries, upload_with_retries


def payload_size(local: Path) -> int:
    """Calcula cuánto se subirá.

    Args:
        local (Path): ``.ffpfsc`` o carpeta LZ4 local.

    Returns:
        int: Bytes del archivo, o la suma de los archivos de la carpeta.
    """
    if local.is_dir():
        return sum(item.size for item in folder_files(local))
    return local.stat().st_size


def payload_pairs(local: Path, remote_part: str) -> list[FilePair]:
    """Empareja cada archivo local con su copia subida, para verificarlos con CRC32.

    Los archivos vacíos se omiten: no hay contenido que comparar.

    Args:
        local (Path): ``.ffpfsc`` o carpeta LZ4 local.
        remote_part (str): Ruta temporal en la PS5.

    Returns:
        list[FilePair]: Pares local/remoto con su tamaño.
    """
    if not local.is_dir():
        return [FilePair(local, remote_part, local.stat().st_size)]
    return [FilePair(item.local, join_remote(remote_part, item.relative), item.size)
            for item in folder_files(local) if item.size]


def upload_payload(factory: ClientFactory, target: ConsoleTarget, local: Path,
                   remote_part: str, hooks: UploadHooks) -> None:
    """Sube el resultado a su ruta temporal, retomando lo que ya estaba.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        local (Path): ``.ffpfsc`` o carpeta LZ4 local.
        remote_part (str): Ruta temporal en la PS5.
        hooks (UploadHooks): Avance, cancelación y reintentos.

    Raises:
        DownloadCancelledError: Si se cancela.
        OSError: Si falla la red tras los reintentos.
    """
    if local.is_dir():
        upload_folder_to(factory, target, local, remote_part, hooks)
        return
    upload_with_retries(factory, target, local, remote_part, hooks.progress,
                        hooks.should_cancel, hooks.on_retry)


def publish_payload(factory: ClientFactory, target: ConsoleTarget, local: Path,
                    plan: ReplacePlan, hooks: UploadHooks) -> None:
    """Da al resultado subido su nombre definitivo (dentro del mismo disco).

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        local (Path): ``.ffpfsc`` o carpeta LZ4 local (para saber cuál de los dos es).
        plan (ReplacePlan): Rutas temporal y definitiva.
        hooks (UploadHooks): Cancelación y aviso de reintentos.

    Raises:
        DownloadCancelledError: Si se cancela.
        OSError: Si falla la red tras los reintentos.
    """
    if local.is_dir():
        rename_remote(factory, target, plan.remote_part, plan.remote_final, hooks)
        return
    publish_with_retries(factory, target, plan.remote_part, plan.remote_final,
                         local.stat().st_size, hooks.should_cancel, hooks.on_retry)


def is_folder_published(factory: ClientFactory, target: ConsoleTarget,
                        plan: ReplacePlan) -> bool:
    """Indica si una carpeta LZ4 ya quedó publicada en un intento anterior.

    Solo tiene sentido con el original ya borrado: la carpeta LZ4 usa el mismo
    nombre que el original, así que si ese nombre existe y la temporal no, es la nueva.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        plan (ReplacePlan): Rutas temporal y definitiva.

    Returns:
        bool: ``True`` si la carpeta definitiva existe y la temporal ya no.
    """
    client = factory(target)
    try:
        client.connect()
        return (remote_exists(client, plan.remote_final)
                and not remote_exists(client, plan.remote_part))
    finally:
        client.close()
