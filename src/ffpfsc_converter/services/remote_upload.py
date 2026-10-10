"""Subida segura de un archivo a la PS5.

El archivo se sube como ``nombre.part`` (ShadowMount+ no lo reconoce), se
reanuda con ``REST`` si ya había una parte, se verifica su tamaño y solo
entonces se renombra al nombre definitivo, dentro de la misma carpeta (el
renombre nunca cruza discos, lo que colgaría la consola).
"""
from __future__ import annotations

import io
import time
from collections.abc import Callable
from pathlib import Path

from ffpfsc_converter.config import (
    FTP_MAX_RESUME_OFFSET,
    PARTIAL_SUFFIX,
    PROGRESS_INTERVAL_SECONDS,
)
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.errors import DownloadCancelledError, TransientError
from ffpfsc_converter.services.remote_client import ClientFactory, RemoteClient
from ffpfsc_converter.services.retry import RetryCallback, with_retries
from ffpfsc_converter.timing import EtaEstimator, SpeedAverage

#: Bytes finales de una subida parcial que se comparan antes de reanudarla.
_RESUME_PROBE_BYTES = 1024 * 1024
#: Recibe ``(hecho, total, unidades_por_segundo, segundos_restantes)``.
ProgressCallback = Callable[[int, int, float, float | None], None]


class UploadVerificationError(TransientError):
    """El tamaño en la PS5 no coincide con el archivo local."""

    def __init__(self, remote_path: str, expected: int, actual: int | None) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            remote_path (str): Archivo remoto verificado.
            expected (int): Tamaño local.
            actual (int | None): Tamaño en la PS5, o ``None`` si no apareció.
        """
        super().__init__(f"La subida de {remote_path} no se pudo verificar: "
                         f"se esperaban {expected} bytes y la PS5 tiene {actual}.")


def part_path(remote_final: str) -> str:
    """Calcula la ruta temporal de una subida.

    Args:
        remote_final (str): Ruta definitiva en la PS5.

    Returns:
        str: La misma ruta con el sufijo ``.part``.
    """
    return remote_final + PARTIAL_SUFFIX


def upload_file(
    client: RemoteClient,
    local: Path,
    remote_part: str,
    on_progress: ProgressCallback,
    should_cancel: Callable[[], bool],
) -> int:
    """Sube un archivo a una ruta temporal, reanudando si ya hay una parte, y lo verifica.

    Args:
        client (RemoteClient): Cliente conectado con permiso de escritura.
        local (Path): Archivo local.
        remote_part (str): Ruta temporal en la PS5.
        on_progress (ProgressCallback): Recibe el avance (con frecuencia limitada).
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.

    Returns:
        int: Tamaño subido y verificado.

    Raises:
        DownloadCancelledError: Si se canceló.
        UploadVerificationError: Si el tamaño remoto no coincide.
    """
    total = local.stat().st_size
    offset = resume_offset(client, local, remote_part, total)
    started = time.monotonic()
    state = {"done": offset, "mark": offset, "time": started}
    average = SpeedAverage()
    estimator = EtaEstimator()

    def on_chunk(size: int) -> None:
        """Suma el bloque enviado, informa el avance y aborta si se canceló.

        Args:
            size (int): Bytes enviados.

        Raises:
            DownloadCancelledError: Si se pidió cancelar.
        """
        if should_cancel():
            raise DownloadCancelledError()
        state["done"] += size
        now = time.monotonic()
        if now - state["time"] >= PROGRESS_INTERVAL_SECONDS:
            speed = average.add((state["done"] - state["mark"]) / (now - state["time"]))
            state["mark"], state["time"] = state["done"], now
            eta = estimator.update(state["done"] - offset, total - state["done"])
            on_progress(state["done"], total, speed, eta)

    if offset < total or total == 0:
        with local.open("rb") as source:
            source.seek(offset)
            client.upload(source, remote_part, offset, on_chunk)
    on_progress(total, total, 0.0, None)
    actual = client.size(remote_part)
    if actual != total:
        raise UploadVerificationError(remote_part, total, actual)
    return total


def resume_offset(client: RemoteClient, local: Path, remote_part: str, total: int) -> int:
    """Decide desde dónde continuar una subida, comprobando que la parte remota sea de este archivo.

    Compara el último tramo del ``.part`` remoto con los mismos bytes del archivo
    local. Si no coinciden (por ejemplo, el juego se volvió a comprimir con otras
    opciones), la subida empieza de cero: reanudar mezclaría dos archivos. Tampoco
    se reanuda por encima de ``FTP_MAX_RESUME_OFFSET``, que la PS5 no sabe retomar.

    Args:
        client (RemoteClient): Cliente conectado.
        local (Path): Archivo local.
        remote_part (str): Ruta temporal en la PS5.
        total (int): Tamaño del archivo local.

    Returns:
        int: Bytes que ya están bien en la PS5 (``0`` = subir desde el principio).
    """
    existing = client.size(remote_part) or 0
    if existing == 0 or existing > total or existing > FTP_MAX_RESUME_OFFSET:
        return 0
    probe = min(_RESUME_PROBE_BYTES, existing)
    remote_tail = io.BytesIO()
    client.download(remote_part, remote_tail, existing - probe, lambda _size: None)
    with local.open("rb") as source:
        source.seek(existing - probe)
        local_tail = source.read(probe)
    return existing if remote_tail.getvalue() == local_tail else 0


def publish(client: RemoteClient, remote_part: str, remote_final: str, size: int) -> None:
    """Renombra la subida verificada a su nombre definitivo y lo comprueba.

    Args:
        client (RemoteClient): Cliente conectado con permiso de escritura.
        remote_part (str): Ruta temporal.
        remote_final (str): Ruta definitiva (misma carpeta).
        size (int): Tamaño esperado.

    Raises:
        UploadVerificationError: Si tras renombrar el tamaño no coincide.
    """
    if client.size(remote_part) is None and client.size(remote_final) == size:
        return  # ya se publicó en un intento anterior que perdió la respuesta
    client.rename(remote_part, remote_final)
    actual = client.size(remote_final)
    if actual != size:
        raise UploadVerificationError(remote_final, size, actual)


def upload_with_retries(
    factory: ClientFactory,
    target: ConsoleTarget,
    local: Path,
    remote_part: str,
    on_progress: ProgressCallback,
    should_cancel: Callable[[], bool],
    on_retry: RetryCallback,
) -> int:
    """Sube un archivo a su ``.part`` reconectando y reanudando tras cortes de conexión.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        local (Path): Archivo local.
        remote_part (str): Ruta temporal en la PS5.
        on_progress (ProgressCallback): Recibe el avance.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.
        on_retry (RetryCallback): Se llama antes de cada reintento.

    Returns:
        int: Tamaño subido y verificado.
    """
    def attempt() -> int:
        """Conecta y sube (reanudando la parte remota si es de este archivo).

        Returns:
            int: Tamaño subido y verificado.
        """
        client = factory(target)
        try:
            client.connect()
            return upload_file(client, local, remote_part, on_progress, should_cancel)
        finally:
            client.close()

    return with_retries(attempt, on_retry, should_cancel)


def publish_with_retries(
    factory: ClientFactory,
    target: ConsoleTarget,
    remote_part: str,
    remote_final: str,
    size: int,
    should_cancel: Callable[[], bool],
    on_retry: RetryCallback,
) -> None:
    """Publica una subida verificada, reintentando tras cortes de conexión.

    Args:
        factory (ClientFactory): Crea el cliente FTP.
        target (ConsoleTarget): FTP con escritura.
        remote_part (str): Ruta temporal.
        remote_final (str): Ruta definitiva.
        size (int): Tamaño esperado.
        should_cancel (Callable[[], bool]): Devuelve ``True`` si hay que cancelar.
        on_retry (RetryCallback): Se llama antes de cada reintento.
    """
    def attempt() -> None:
        """Conecta, renombra y verifica (idempotente)."""
        client = factory(target)
        try:
            client.connect()
            publish(client, remote_part, remote_final, size)
        finally:
            client.close()

    with_retries(attempt, on_retry, should_cancel)
