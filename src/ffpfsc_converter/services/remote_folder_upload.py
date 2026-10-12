"""Subida de una carpeta completa a la PS5 (por ejemplo, un juego en formato LZ4).

Todo va primero a ``<destino>/<nombre>.part/``: cada archivo con su ``.part``,
verificación de tamaño y reintentos (como una subida normal). Solo al terminar se
renombra la carpeta a su nombre definitivo, dentro del mismo disco. Así un corte
nunca deja en ``homebrew`` una carpeta a medias que parezca un juego completo, y al
reintentar se saltan los archivos que ya estaban.
"""
from __future__ import annotations

import posixpath
from collections.abc import Callable, Sequence
from pathlib import Path

from ffpfsc_converter.config import PARTIAL_SUFFIX
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.errors import RemoteFolderExistsError
from ffpfsc_converter.infrastructure.ftp import join_remote
from ffpfsc_converter.services.remote_client import ClientFactory, RemoteClient
from ffpfsc_converter.services.remote_folder_files import (
    FolderFile,
    UploadHooks,
    folder_files,
    offset_hooks,
    remote_dirs,
)
from ffpfsc_converter.services.remote_upload import (
    part_path,
    publish_with_retries,
    upload_with_retries,
)
from ffpfsc_converter.services.retry import with_retries


def upload_folder(factory: ClientFactory, target: ConsoleTarget, folder: Path,
                  remote_dir: str, hooks: UploadHooks) -> str:
    """Sube una carpeta completa y la publica con su nombre al final.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        folder (Path): Carpeta local.
        remote_dir (str): Carpeta de la PS5 donde quedará.
        hooks (UploadHooks): Avance, cancelación y reintentos.

    Returns:
        str: Ruta remota definitiva de la carpeta.

    Raises:
        RemoteFolderExistsError: Si ya hay una carpeta con ese nombre (no se sobrescribe).
        DownloadCancelledError: Si se canceló (lo subido queda para reintentar).
        OSError: Si falla la red tras los reintentos.
    """
    final = join_remote(remote_dir, folder.name)
    _with_client(factory, target, hooks,
                 lambda client: _ensure_free(client, remote_dir, folder.name))
    upload_folder_to(factory, target, folder, final + PARTIAL_SUFFIX, hooks)
    rename_remote(factory, target, final + PARTIAL_SUFFIX, final, hooks)
    return final


def upload_folder_to(factory: ClientFactory, target: ConsoleTarget, folder: Path,
                     staging: str, hooks: UploadHooks) -> int:
    """Sube el contenido de una carpeta a una carpeta temporal de la PS5 (sin publicarla).

    Lo que ya estaba completo en ``staging`` (de un intento anterior) se salta.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        folder (Path): Carpeta local.
        staging (str): Carpeta temporal en la PS5 (se crea si falta).
        hooks (UploadHooks): Avance, cancelación y reintentos.

    Returns:
        int: Bytes de la carpeta.

    Raises:
        DownloadCancelledError: Si se canceló.
        OSError: Si falla la red tras los reintentos.
    """
    files = folder_files(folder)
    present = _with_client(factory, target, hooks,
                           lambda client: _prepare_staging(client, staging, files))
    total, done = sum(f.size for f in files), 0
    for item in files:
        if present.get(item.relative) != item.size:
            _upload_item(factory, target, item, staging, offset_hooks(hooks, done, total))
        done += item.size
    return total


def rename_remote(factory: ClientFactory, target: ConsoleTarget, source: str, dest: str,
                  hooks: UploadHooks) -> None:
    """Renombra una carpeta en la PS5 (dentro del mismo disco), reintentando tras cortes.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        source (str): Ruta actual.
        dest (str): Ruta nueva.
        hooks (UploadHooks): Cancelación y aviso de reintentos.
    """
    _with_client(factory, target, hooks, lambda client: _rename_once(client, source, dest))


def remote_exists(client: RemoteClient, path: str) -> bool:
    """Indica si existe un archivo o carpeta en la PS5.

    Args:
        client (RemoteClient): Cliente conectado.
        path (str): Ruta remota absoluta.

    Returns:
        bool: ``True`` si su carpeta contiene ese nombre.
    """
    parent = posixpath.dirname(path) or "/"
    return any(entry.name == posixpath.basename(path) for entry in client.list_dir(parent))


def _rename_once(client: RemoteClient, source: str, dest: str) -> None:
    """Renombra, salvo que ya esté hecho (la respuesta de un intento anterior se perdió).

    Args:
        client (RemoteClient): Cliente conectado con escritura.
        source (str): Ruta actual.
        dest (str): Ruta nueva.
    """
    if not remote_exists(client, source) and remote_exists(client, dest):
        return
    client.rename(source, dest)


def _ensure_free(client: RemoteClient, remote_dir: str, name: str) -> None:
    """Comprueba que no haya ya algo con ese nombre en el destino.

    Args:
        client (RemoteClient): Cliente conectado.
        remote_dir (str): Carpeta de destino.
        name (str): Nombre de la carpeta que se sube.

    Raises:
        RemoteFolderExistsError: Si ya existe ``<destino>/<name>``.
    """
    if any(entry.name == name for entry in client.list_dir(remote_dir)):
        raise RemoteFolderExistsError(join_remote(remote_dir, name))


def _prepare_staging(client: RemoteClient, staging: str,
                     files: Sequence[FolderFile]) -> dict[str, int]:
    """Crea la carpeta temporal y sus subcarpetas, y mira qué archivos ya están completos.

    Args:
        client (RemoteClient): Cliente conectado con escritura.
        staging (str): Carpeta temporal en la PS5.
        files (Sequence[FolderFile]): Archivos (para saber qué subcarpetas crear).

    Returns:
        dict[str, int]: Archivos ya publicados en la carpeta temporal (ruta relativa →
        tamaño), de un intento anterior.
    """
    present = ({entry.path[len(staging) + 1:]: entry.size for entry in client.walk(staging)
                if not entry.is_dir} if remote_exists(client, staging) else {})
    client.make_dir(staging)
    for relative in remote_dirs(files):
        client.make_dir(join_remote(staging, relative))
    return present


def _upload_item(factory: ClientFactory, target: ConsoleTarget, item: FolderFile,
                 staging: str, hooks: UploadHooks) -> None:
    """Sube un archivo dentro de la carpeta temporal (como ``.part``, verificado y publicado).

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        item (FolderFile): Archivo a subir.
        staging (str): Carpeta temporal en la PS5.
        hooks (UploadHooks): Avance ya desplazado al total de la carpeta.
    """
    remote = join_remote(staging, item.relative)
    size = upload_with_retries(factory, target, item.local, part_path(remote), hooks.progress,
                               hooks.should_cancel, hooks.on_retry)
    publish_with_retries(factory, target, part_path(remote), remote, size,
                         hooks.should_cancel, hooks.on_retry)


def _with_client(factory: ClientFactory, target: ConsoleTarget, hooks: UploadHooks,
                 action: Callable[[RemoteClient], object]) -> object:
    """Ejecuta una operación con un cliente nuevo, reintentando tras cortes de conexión.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        hooks (UploadHooks): Cancelación y aviso de reintentos.
        action (Callable[[RemoteClient], object]): Operación con el cliente conectado.

    Returns:
        object: Lo que devuelva ``action``.
    """
    def attempt() -> object:
        """Conecta, ejecuta la operación y cierra.

        Returns:
            object: Resultado de la operación.
        """
        client = factory(target)
        try:
            client.connect()
            return action(client)
        finally:
            client.close()

    return with_retries(attempt, hooks.on_retry, hooks.should_cancel)
