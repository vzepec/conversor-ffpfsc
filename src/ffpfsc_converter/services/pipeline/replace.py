"""Reemplazo en la PS5: espacio, subida verificada, borrado del original y renombre.

Sirve para un ``.ffpfsc`` y para una carpeta LZ4. Orden seguro (acordado): se sube
como ``.part``, se verifica (tamaño y CRC32) y recién entonces se borra el original
y se renombra. Solo si la PS5 no tiene espacio para ambos a
la vez se borra antes, con confirmación explícita (la copia local sirve de respaldo).
"""
from __future__ import annotations

import posixpath
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ffpfsc_converter.domain.pipeline import PipelineStage, ReplacePlan, SpaceStrategy
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.errors import ConverterError
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.infrastructure.ava1.console import JobStatus, delete_tree, free_space
from ffpfsc_converter.services.console_access import (
    ConsoleAccess,
    RestoreCallback,
    writable_ftp,
)
from ffpfsc_converter.services.integrity import IntegrityError, verify_files
from ffpfsc_converter.services.pipeline.payload import (
    is_folder_published,
    payload_pairs,
    payload_size,
    publish_payload,
    upload_payload,
)
from ffpfsc_converter.services.pipeline.plan import choose_strategy
from ffpfsc_converter.services.remote_client import ClientFactory
from ffpfsc_converter.services.remote_folder_files import UploadHooks
from ffpfsc_converter.services.remote_upload import ProgressCallback
from ffpfsc_converter.services.retry import RetryCallback


class ConsoleSpaceError(ConverterError):
    """La PS5 no tiene espacio para el juego comprimido ni borrando el original."""

    def __init__(self, needed: int, usable: int) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            needed (int): Tamaño a subir.
            usable (int): Espacio usable en la PS5.
        """
        super().__init__(f"La PS5 no tiene espacio: se necesitan {format_size(needed)} y hay "
                         f"{format_size(usable)} disponibles (incluso borrando el original).")


class ReplaceDeclinedError(ConverterError):
    """El usuario no aceptó borrar el original antes de subir."""

    def __init__(self) -> None:
        """Crea el error con un mensaje para el usuario."""
        super().__init__("Reemplazo cancelado: no se borró nada en la PS5.")


@dataclass
class ReplaceContext:
    """Todo lo que necesita el reemplazo.

    Attributes:
        access (ConsoleAccess): Acceso AVA1 a la consola.
        client_factory (ClientFactory): Crea el cliente FTP.
        host (str): Dirección de la PS5.
        port (int): Puerto FTP.
        plan (ReplacePlan): Qué se borra y dónde se sube.
        local_output (Path): ``.ffpfsc`` o carpeta LZ4 local.
        original_size (int): Tamaño del original en la PS5.
        stage (Callable[[PipelineStage, str], None]): Avisa el cambio de etapa.
        progress (ProgressCallback): Avance de la subida.
        confirm (Callable[[str], bool]): Pide una confirmación al usuario.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.
        on_restored (RestoreCallback): Recibe el FTP de solo lectura final (o ``None``).
        on_retry (RetryCallback): Avisa cada reintento automático tras un corte.
        original_deleted (bool): ``True`` una vez borrado el original (también si se
            borró en un intento anterior; así no se vuelve a borrar).
    """

    access: ConsoleAccess
    client_factory: ClientFactory
    host: str
    port: int
    plan: ReplacePlan
    local_output: Path
    original_size: int
    stage: Callable[[PipelineStage, str], None]
    progress: ProgressCallback
    confirm: Callable[[str], bool]
    should_cancel: Callable[[], bool]
    on_restored: RestoreCallback
    on_retry: RetryCallback
    original_deleted: bool = False


def replace_on_console(ctx: ReplaceContext) -> int:
    """Sube el juego comprimido y reemplaza el original en la PS5.

    Args:
        ctx (ReplaceContext): Datos y callbacks del reemplazo.

    Returns:
        int: Bytes publicados.

    Raises:
        ConsoleSpaceError: Si no hay espacio ni borrando el original.
        ReplaceDeclinedError: Si el usuario no acepta borrar antes de subir.
        DownloadCancelledError: Si se cancela durante la subida.
        OSError: Si falla la comunicación con la PS5.
    """
    size = payload_size(ctx.local_output)
    strategy = _check_space(ctx, size)
    hooks = UploadHooks(ctx.progress, ctx.should_cancel, ctx.on_retry)
    with writable_ftp(ctx.access, ctx.host, ctx.port, ctx.on_restored) as target:
        if not _already_published(ctx, target):
            if strategy is SpaceStrategy.DELETE_FIRST and not ctx.original_deleted:
                _delete_original(ctx)
            ctx.stage(PipelineStage.UPLOAD, ctx.plan.remote_part)
            upload_payload(ctx.client_factory, target, ctx.local_output, ctx.plan.remote_part,
                           hooks)
            _verify_upload(ctx)
            if not ctx.original_deleted:
                _delete_original(ctx)
            ctx.stage(PipelineStage.RENAME, ctx.plan.remote_final)
            publish_payload(ctx.client_factory, target, ctx.local_output, ctx.plan, hooks)
        ctx.stage(PipelineStage.RESTORE_FTP, "")
    return size


def _already_published(ctx: ReplaceContext, target: ConsoleTarget) -> bool:
    """Indica si una carpeta LZ4 ya se publicó en un intento anterior (no hay que subirla).

    Args:
        ctx (ReplaceContext): Contexto del reemplazo.
        target (ConsoleTarget): FTP con escritura.

    Returns:
        bool: ``True`` solo con una carpeta, el original ya borrado y la nueva en su lugar.
    """
    return (ctx.local_output.is_dir() and ctx.original_deleted
            and is_folder_published(ctx.client_factory, target, ctx.plan))


def _check_space(ctx: ReplaceContext, size: int) -> SpaceStrategy:
    """Consulta el espacio de la PS5 y decide el orden del reemplazo.

    Args:
        ctx (ReplaceContext): Contexto del reemplazo.
        size (int): Bytes a subir.

    Returns:
        SpaceStrategy: ``UPLOAD_FIRST`` o ``DELETE_FIRST`` (confirmado por el usuario).

    Raises:
        ConsoleSpaceError: Si no cabe de ninguna forma.
        ReplaceDeclinedError: Si el usuario no acepta borrar antes.
    """
    ctx.stage(PipelineStage.CHECK_SPACE, "")
    session = ctx.access.open_session(ctx.host)
    try:
        space = free_space(session, posixpath.dirname(ctx.plan.remote_final) or "/")
    finally:
        session.close()
    freeable = 0 if ctx.original_deleted else ctx.original_size
    strategy = choose_strategy(space.usable, size, 0, freeable)
    if strategy is SpaceStrategy.INSUFFICIENT:
        raise ConsoleSpaceError(size, space.usable)
    if strategy is SpaceStrategy.DELETE_FIRST and not ctx.confirm(
            f"La PS5 solo tiene {format_size(space.usable)} libres y el juego comprimido "
            f"ocupa {format_size(size)}.\n\nPara que quepa hay que BORRAR PRIMERO el original:\n"
            f"{ctx.plan.original.path}\n\nTu copia local se conserva hasta verificar la subida. "
            "¿Borrar el original y continuar?"):
        raise ReplaceDeclinedError()
    return strategy


def _verify_upload(ctx: ReplaceContext) -> None:
    """Comprueba con CRC32 que lo subido es idéntico a lo local, archivo por archivo.

    Lo que difiere se borra en la PS5 para que el reintento lo vuelva a subir; el
    original no se toca.

    Args:
        ctx (ReplaceContext): Contexto del reemplazo.

    Raises:
        IntegrityError: Si el contenido no coincide.
        DownloadCancelledError: Si se canceló.
    """
    ctx.stage(PipelineStage.VERIFY_UPLOAD, ctx.plan.remote_part)
    pairs = payload_pairs(ctx.local_output, ctx.plan.remote_part)
    session = ctx.access.open_session(ctx.host)
    try:
        bad = verify_files(session, pairs,
                           lambda done, total: ctx.progress(done, total, 0.0, None),
                           ctx.should_cancel)
        for pair in bad:
            delete_tree(session, pair.remote, lambda _status: None)
    finally:
        session.close()
    if bad:
        raise IntegrityError([pair.local.name for pair in bad], "la subida")


def _delete_original(ctx: ReplaceContext) -> None:
    """Borra la carpeta o imagen original con el helper.

    Args:
        ctx (ReplaceContext): Contexto del reemplazo; marca ``original_deleted``.
    """
    path = ctx.plan.original.path
    ctx.stage(PipelineStage.DELETE_ORIGINAL, path)

    def report(status: JobStatus) -> None:
        """Informa el avance del borrado.

        Args:
            status (JobStatus): Estado de la tarea en la consola.
        """
        if status.files_total:
            ctx.progress(status.files_done, status.files_total, 0.0, None)

    session = ctx.access.open_session(ctx.host)
    try:
        delete_tree(session, path, report)
    finally:
        session.close()
    ctx.original_deleted = True
