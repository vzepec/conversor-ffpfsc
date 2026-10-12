"""Operaciones que modifican la PS5 desde el explorador: eliminar y subir archivos o carpetas.

Ambas corren en un hilo de fondo. El borrado lo ejecuta el helper (``job.run``
DELETE), que protege raíces, carpetas de primer nivel y puntos de montaje. La
subida activa la escritura del FTP solo mientras dura.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Sequence
from pathlib import Path

from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.pipeline_events import (
    RemoteDeleted,
    RemoteDeleteProgress,
    UploadFinished,
    UploadProgress,
)
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.domain.remote_events import RemoteError, TransferRetrying
from ffpfsc_converter.errors import ConverterError, DownloadCancelledError
from ffpfsc_converter.infrastructure.ava1.console import delete_tree
from ffpfsc_converter.infrastructure.ftp import FTP_ERRORS, FtpClient, join_remote
from ffpfsc_converter.services.console_access import (
    ConsoleAccess,
    restore_notifier,
    writable_ftp,
)
from ffpfsc_converter.services.launch_errors import describe_launch_error
from ffpfsc_converter.services.remote_client import ClientFactory
from ffpfsc_converter.services.remote_folder_upload import UploadHooks, upload_folder
from ffpfsc_converter.services.remote_upload import (
    part_path,
    publish_with_retries,
    upload_with_retries,
)


class RemoteChanges:
    """Elimina y sube archivos en la PS5 sin bloquear la interfaz."""

    def __init__(
        self, emit: EventSink, access: ConsoleAccess, client_factory: ClientFactory = FtpClient
    ) -> None:
        """Prepara el servicio.

        Args:
            emit (EventSink): Destino de los eventos.
            access (ConsoleAccess): Acceso AVA1 a la consola.
            client_factory (ClientFactory): Crea el cliente FTP.
        """
        self._emit = emit
        self._access = access
        self._factory = client_factory
        self._cancel = threading.Event()
        self.busy = False

    def delete(self, host: str, paths: Sequence[str]) -> threading.Thread:
        """Borra archivos o carpetas completas en la PS5.

        Args:
            host (str): Dirección de la PS5.
            paths (Sequence[str]): Rutas remotas absolutas.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        return self._spawn(self._do_delete, host, list(paths))

    def upload(self, host: str, port: int, files: Sequence[Path], remote_dir: str,
               ids: Sequence[str] | None = None) -> list[str]:
        """Sube archivos o carpetas locales a una carpeta de la PS5.

        Args:
            host (str): Dirección de la PS5.
            port (int): Puerto FTP.
            files (Sequence[Path]): Archivos o carpetas locales (una carpeta es una sola fila).
            remote_dir (str): Carpeta remota de destino.
            ids (Sequence[str] | None): Filas a reutilizar (reintento manual); ``None`` = nuevas.

        Returns:
            list[str]: Identificador de cada subida (para su fila en la tabla).
        """
        upload_ids = list(ids) if ids is not None else [uuid.uuid4().hex for _ in files]
        items = list(zip(upload_ids, files, strict=True))
        self._spawn(self._do_upload, host, port, items, remote_dir)
        return [upload_id for upload_id, _ in items]

    def cancel(self) -> None:
        """Pide cancelar la subida en curso."""
        self._cancel.set()

    def _spawn(self, target: object, *args: object) -> threading.Thread:
        """Ejecuta una operación en un hilo daemon, marcando el servicio como ocupado.

        Args:
            target (object): Método a ejecutar.
            *args (object): Argumentos del método.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        self.busy = True
        self._cancel.clear()

        def run() -> None:
            """Ejecuta la operación y libera el servicio al terminar."""
            try:
                target(*args)  # type: ignore[operator]
            finally:
                self.busy = False

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def _do_delete(self, host: str, paths: list[str]) -> None:
        """Borra cada ruta con el helper y publica el resultado.

        Args:
            host (str): Dirección de la PS5.
            paths (list[str]): Rutas remotas.
        """
        try:
            session = self._access.open_session(host)
            try:
                for path in paths:
                    delete_tree(session, path, lambda s, p=path: self._emit(
                        RemoteDeleteProgress(p, s.files_done, s.files_total)))
            finally:
                session.close()
        except (OSError, ValueError, ConverterError) as exc:
            self._emit(RemoteError(describe_launch_error(exc, host, "borrar")))
            return
        self._emit(RemoteDeleted(tuple(paths)))

    def _do_upload(self, host: str, port: int, items: list[tuple[str, Path]],
                   remote_dir: str) -> None:
        """Activa la escritura, sube cada archivo y restaura el FTP de solo lectura.

        Si un archivo falla tras los reintentos automáticos, él y los siguientes
        quedan marcados como fallidos (para reintentarlos a mano).

        Args:
            host (str): Dirección de la PS5.
            port (int): Puerto FTP.
            items (list[tuple[str, Path]]): Pares (id de subida, archivo local).
            remote_dir (str): Carpeta remota de destino.
        """
        pending = list(items)
        try:
            with writable_ftp(self._access, host, port,
                              restore_notifier(self._emit, host, port)) as target:
                while pending:
                    upload_id, local = pending[0]
                    self._upload_one(target, upload_id, local, remote_dir)
                    pending.pop(0)
        except DownloadCancelledError:
            self._fail(pending, "✖ Cancelada (se puede reintentar)")
            self._emit(RemoteError("Subida cancelada. Usa «Reintentar fallidas» para reanudarla."))
        except (*FTP_ERRORS, ValueError, ConverterError) as exc:
            message = describe_launch_error(exc, host, "subir")
            self._fail(pending, message.splitlines()[0])
            self._emit(RemoteError(message))

    def _fail(self, pending: list[tuple[str, Path]], message: str) -> None:
        """Marca como fallidas las subidas que no terminaron.

        Args:
            pending (list[tuple[str, Path]]): Subidas sin terminar (la primera es la que falló).
            message (str): Causa para la primera; el resto indica que no se iniciaron.
        """
        for index, (upload_id, _local) in enumerate(pending):
            self._emit(UploadFinished(upload_id, False,
                                      message if index == 0 else "No se inició"))

    def _upload_one(
        self, target: ConsoleTarget, upload_id: str, local: Path, remote_dir: str
    ) -> None:
        """Sube un archivo como ``.part`` (con reintentos), lo verifica y lo publica.

        Una carpeta se sube completa en ``<nombre>.part/`` y se publica al final.

        Args:
            target (ConsoleTarget): FTP con escritura.
            upload_id (str): Identificador de la fila.
            local (Path): Archivo o carpeta local.
            remote_dir (str): Carpeta remota.
        """
        final = join_remote(remote_dir, local.name)
        if not local.is_dir() and self._is_already_uploaded(target, local, final):
            self._emit(UploadFinished(upload_id, True, f"{final} (ya estaba en la PS5)"))
            return

        def on_retry(attempt: int, max_attempts: int, exc: BaseException) -> None:
            """Avisa que se reintentará la subida.

            Args:
                attempt (int): Reintento que comienza.
                max_attempts (int): Reintentos máximos.
                exc (BaseException): Error que provocó el reintento.
            """
            reason = describe_launch_error(exc, target.host, "subir").splitlines()[0]
            self._emit(TransferRetrying(upload_id, attempt, max_attempts, reason))

        hooks = UploadHooks(
            lambda d, t, s, e: self._emit(UploadProgress(upload_id, local.name, d, t, s, e)),
            self._cancel.is_set, on_retry)
        if local.is_dir():
            final = upload_folder(self._factory, target, local, remote_dir, hooks)
            self._emit(UploadFinished(upload_id, True, final))
            return
        size = upload_with_retries(self._factory, target, local, part_path(final),
                                   hooks.progress, hooks.should_cancel, on_retry)
        publish_with_retries(self._factory, target, part_path(final), final, size,
                             self._cancel.is_set, on_retry)
        self._emit(UploadFinished(upload_id, True, final))

    def _is_already_uploaded(self, target: ConsoleTarget, local: Path, final: str) -> bool:
        """Comprueba si el archivo definitivo ya está en la PS5 con el mismo tamaño.

        Evita volver a enviar decenas de GB cuando el juego ya se subió antes
        (por ejemplo, al pulsar «Subir completados a la PS5» dos veces).

        Args:
            target (ConsoleTarget): FTP con escritura.
            local (Path): Archivo local.
            final (str): Ruta definitiva en la PS5.

        Returns:
            bool: ``True`` si ya existe un archivo del mismo tamaño.
        """
        client = self._factory(target)
        try:
            client.connect()
            return client.size(final) == local.stat().st_size
        finally:
            client.close()
