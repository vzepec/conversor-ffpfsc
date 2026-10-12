"""Subida de una carpeta completa a la PS5 (por ejemplo, un juego en formato LZ4).

Todo va primero a ``<destino>/<nombre>.part/``: cada archivo con su ``.part``,
verificación de tamaño y reintentos (como una subida normal). Solo al terminar se
renombra la carpeta a su nombre definitivo, dentro del mismo disco. Así un corte
nunca deja en ``homebrew`` una carpeta a medias que parezca un juego completo, y al
reintentar se saltan los archivos que ya estaban.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ffpfsc_converter.config import PARTIAL_SUFFIX
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.errors import RemoteFolderExistsError
from ffpfsc_converter.infrastructure.ftp import join_remote
from ffpfsc_converter.services.remote_client import ClientFactory, RemoteClient
from ffpfsc_converter.services.remote_upload import (
    ProgressCallback,
    part_path,
    publish_with_retries,
    upload_with_retries,
)
from ffpfsc_converter.services.retry import RetryCallback, with_retries


@dataclass(frozen=True)
class FolderFile:
    """Archivo de la carpeta que se sube.

    Attributes:
        local (Path): Archivo en este equipo.
        relative (str): Ruta dentro de la carpeta, con ``/``.
        size (int): Bytes.
    """

    local: Path
    relative: str
    size: int


@dataclass(frozen=True)
class UploadHooks:
    """Cómo informa y se controla una subida.

    Attributes:
        progress (ProgressCallback): Avance (hecho, total, velocidad, segundos restantes).
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.
        on_retry (RetryCallback): Se llama antes de cada reintento.
    """

    progress: ProgressCallback
    should_cancel: Callable[[], bool]
    on_retry: RetryCallback


def folder_files(folder: Path) -> list[FolderFile]:
    """Lista los archivos de una carpeta (sin seguir enlaces simbólicos), en orden.

    Args:
        folder (Path): Carpeta local.

    Returns:
        list[FolderFile]: Archivos con su ruta relativa y tamaño.
    """
    found: list[FolderFile] = []
    for dirpath, _dirs, names in os.walk(folder):
        for name in names:
            path = Path(dirpath, name)
            if path.is_file() and not path.is_symlink():
                found.append(FolderFile(path, path.relative_to(folder).as_posix(),
                                        path.stat().st_size))
    return sorted(found, key=lambda f: f.relative)


def remote_dirs(files: Sequence[FolderFile]) -> list[str]:
    """Calcula las subcarpetas que hay que crear, de las más externas a las internas.

    Args:
        files (Sequence[FolderFile]): Archivos de la carpeta.

    Returns:
        list[str]: Rutas relativas de carpetas (sin la raíz).
    """
    dirs = {str(parent) for f in files for parent in PurePosixPath(f.relative).parents}
    dirs.discard(".")
    return sorted(dirs, key=lambda d: (d.count("/"), d))


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
    staging = final + PARTIAL_SUFFIX
    files = folder_files(folder)
    present = _with_client(factory, target, hooks,
                           lambda client: _prepare(client, remote_dir, folder.name, files))
    total, done = sum(f.size for f in files), 0
    for item in files:
        if present.get(item.relative) != item.size:  # lo completo de un intento anterior se salta
            _upload_item(factory, target, item, staging, _offset(hooks, done, total))
        done += item.size
    _with_client(factory, target, hooks, lambda client: client.rename(staging, final))
    return final


def _prepare(client: RemoteClient, remote_dir: str, name: str,
             files: Sequence[FolderFile]) -> dict[str, int]:
    """Comprueba que el destino esté libre, crea la carpeta temporal y mira qué ya está.

    Args:
        client (RemoteClient): Cliente conectado con escritura.
        remote_dir (str): Carpeta de destino.
        name (str): Nombre de la carpeta que se sube.
        files (Sequence[FolderFile]): Archivos (para saber qué subcarpetas crear).

    Returns:
        dict[str, int]: Archivos que ya están publicados en la carpeta temporal (ruta
        relativa → tamaño), de un intento anterior.

    Raises:
        RemoteFolderExistsError: Si ya existe ``<destino>/<name>``.
    """
    names = {entry.name for entry in client.list_dir(remote_dir)}
    if name in names:
        raise RemoteFolderExistsError(join_remote(remote_dir, name))
    staging = join_remote(remote_dir, name) + PARTIAL_SUFFIX
    present = ({entry.path[len(staging) + 1:]: entry.size for entry in client.walk(staging)
                if not entry.is_dir} if f"{name}{PARTIAL_SUFFIX}" in names else {})
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


def _offset(hooks: UploadHooks, done: int, total: int) -> UploadHooks:
    """Adapta el avance de un archivo al de la carpeta completa.

    Args:
        hooks (UploadHooks): Avance de la carpeta.
        done (int): Bytes de los archivos ya subidos.
        total (int): Bytes de toda la carpeta.

    Returns:
        UploadHooks: Los mismos controles con el avance desplazado.
    """
    def progress(file_done: int, _file_total: int, speed: float, _eta: float | None) -> None:
        """Informa el avance total con su tiempo restante.

        Args:
            file_done (int): Bytes subidos del archivo actual.
            _file_total (int): Tamaño del archivo actual (no se usa).
            speed (float): Velocidad en bytes por segundo.
            _eta (float | None): Restante del archivo (se recalcula para la carpeta).
        """
        current = done + file_done
        eta = (total - current) / speed if speed > 0 else None
        hooks.progress(current, total, speed, eta)

    return UploadHooks(progress, hooks.should_cancel, hooks.on_retry)


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
