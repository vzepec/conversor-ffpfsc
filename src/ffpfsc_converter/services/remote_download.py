"""Descarga de un elemento de la PS5: espacio local, transferencia y reintentos.

Lo usan la cola de descargas (``DownloadRunner``) y el pipeline de conversión.
"""
from __future__ import annotations

from collections.abc import Callable

from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.remote import ConsoleTarget, DownloadJob
from ffpfsc_converter.domain.remote_events import TransferRetrying
from ffpfsc_converter.errors import ConverterError, DownloadCancelledError
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.infrastructure.filesystem import free_space
from ffpfsc_converter.services.download_planner import (
    DownloadPlan,
    bytes_already_local,
    plan_download,
)
from ffpfsc_converter.services.file_download import LocalWriteError, download_file
from ffpfsc_converter.services.progress_meter import ProgressMeter
from ffpfsc_converter.services.remote_client import ClientFactory, RemoteClient
from ffpfsc_converter.services.remote_errors import describe_error
from ffpfsc_converter.services.retry import with_retries


class NotEnoughSpaceError(ConverterError):
    """No hay espacio en este equipo para completar la descarga."""

    def __init__(self, needed: int, free: int) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            needed (int): Bytes que faltan por descargar.
            free (int): Bytes libres en la carpeta de destino.
        """
        super().__init__(
            f"No hay espacio suficiente en este equipo: faltan {format_size(needed)} "
            f"y hay {format_size(free)} libres."
        )


def download_with_retries(
    factory: ClientFactory,
    target: ConsoleTarget,
    job: DownloadJob,
    emit: EventSink,
    should_cancel: Callable[[], bool],
) -> int:
    """Descarga un trabajo reconectando y reanudando tras cortes de conexión.

    Args:
        factory (ClientFactory): Crea el cliente remoto.
        target (ConsoleTarget): Consola de origen.
        job (DownloadJob): Descarga.
        emit (EventSink): Destino de ``DownloadProgress`` y ``TransferRetrying``.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Returns:
        int: Archivos descargados u omitidos por estar completos.
    """
    def attempt() -> int:
        """Conecta y descarga (reanudando lo que ya esté en disco).

        Returns:
            int: Archivos descargados u omitidos.
        """
        client = factory(target)
        try:
            client.connect()
            return transfer_job(client, job, emit, should_cancel)
        finally:
            client.close()

    def on_retry(attempt_number: int, max_attempts: int, exc: BaseException) -> None:
        """Avisa que se reintentará la descarga.

        Args:
            attempt_number (int): Reintento que comienza.
            max_attempts (int): Reintentos máximos.
            exc (BaseException): Error que provocó el reintento.
        """
        reason = describe_error(exc, target, f"descargar {job.entry.name}").splitlines()[0]
        emit(TransferRetrying(job.id, attempt_number, max_attempts, reason))

    return with_retries(attempt, on_retry, should_cancel)


def transfer_job(
    client: RemoteClient,
    job: DownloadJob,
    emit: EventSink,
    should_cancel: Callable[[], bool],
) -> int:
    """Planifica y descarga todos los archivos de un trabajo (bloqueante).

    Args:
        client (RemoteClient): Cliente conectado.
        job (DownloadJob): Descarga; se actualizan ``total_bytes`` y ``done_bytes``.
        emit (EventSink): Destino de los eventos ``DownloadProgress``.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Returns:
        int: Cantidad de archivos descargados u omitidos por estar completos.

    Raises:
        DownloadCancelledError: Si se canceló.
        NotEnoughSpaceError: Si no cabe en el disco local.
        LocalWriteError: Si no se pudo crear una carpeta local.
    """
    plan = plan_download(client, job.entry, job.destination)
    job.total_bytes, job.done_bytes = plan.total_bytes, 0
    job.files = list(plan.files)
    _check_space(plan, job)
    for directory in plan.directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise LocalWriteError(directory, exc) from exc
    meter = ProgressMeter(job, emit)
    for transfer in plan.files:
        if should_cancel():
            raise DownloadCancelledError()
        download_file(client, transfer, meter, should_cancel)
    meter.publish(job.entry.name)
    return len(plan.files)


def _check_space(plan: DownloadPlan, job: DownloadJob) -> None:
    """Comprueba que lo que falta por descargar cabe en el disco local.

    Args:
        plan (DownloadPlan): Plan de descarga.
        job (DownloadJob): Descarga en curso (define la carpeta de destino).

    Raises:
        NotEnoughSpaceError: Si el espacio libre no alcanza.
        LocalWriteError: Si no se pudo crear o consultar la carpeta de destino.
    """
    needed = plan.total_bytes - bytes_already_local(plan)
    try:
        job.destination.mkdir(parents=True, exist_ok=True)
        free = free_space(job.destination)
    except OSError as exc:
        raise LocalWriteError(job.destination, exc) from exc
    if needed > free:
        raise NotEnoughSpaceError(needed, free)
