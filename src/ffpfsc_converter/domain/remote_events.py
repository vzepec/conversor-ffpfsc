"""Eventos que publican los servicios del explorador de la PS5.

Igual que los eventos de conversión, se publican desde hilos de fondo y la
interfaz los consume en su propio hilo.
"""
from __future__ import annotations

from dataclasses import dataclass

from ffpfsc_converter.domain.remote import (
    ConsoleTarget,
    DownloadJob,
    DownloadResult,
    RemoteEntry,
    StorageVolume,
)


@dataclass(frozen=True)
class RemoteConnected:
    """Se estableció la conexión con la PS5.

    Attributes:
        target (ConsoleTarget): Consola conectada.
    """

    target: ConsoleTarget


@dataclass(frozen=True)
class RemoteDisconnected:
    """Se cerró la conexión con la PS5."""


@dataclass(frozen=True)
class RemoteListing:
    """Contenido de una carpeta de la PS5.

    Attributes:
        path (str): Carpeta listada.
        entries (tuple[RemoteEntry, ...]): Carpetas primero, luego archivos, por nombre.
    """

    path: str
    entries: tuple[RemoteEntry, ...]


@dataclass(frozen=True)
class RemoteError:
    """Falló una operación del explorador.

    Attributes:
        message (str): Descripción para el usuario.
    """

    message: str


@dataclass(frozen=True)
class PairingCodeRequired:
    """La PS5 muestra un código de emparejamiento y hay que pedírselo al usuario.

    Attributes:
        console_name (str): Nombre de la consola, para el mensaje.
    """

    console_name: str


@dataclass(frozen=True)
class StorageUpdated:
    """Se consultó el espacio de las unidades de la PS5.

    Attributes:
        volumes (tuple[StorageVolume, ...]): Unidades montadas; vacío si falló la consulta.
        error (str): Motivo por el que no se pudo consultar; vacío si funcionó.
    """

    volumes: tuple[StorageVolume, ...]
    error: str = ""


@dataclass(frozen=True)
class FtpReady:
    """El FTP de la PS5 está activo y listo para conectarse.

    Attributes:
        target (ConsoleTarget): Datos de conexión, con las credenciales del servidor.
        started (bool): ``True`` si la app acaba de iniciarlo mediante el helper.
    """

    target: ConsoleTarget
    started: bool


@dataclass(frozen=True)
class FtpLoginRefused:
    """El FTP rechazó las credenciales (lo inició otro programa con otras).

    Attributes:
        target (ConsoleTarget): Consola cuyo FTP rechazó el inicio de sesión.
    """

    target: ConsoleTarget


@dataclass(frozen=True)
class DownloadStarted:
    """Comenzó una descarga.

    Attributes:
        job (DownloadJob): Descarga en curso.
    """

    job: DownloadJob


@dataclass(frozen=True)
class DownloadProgress:
    """Avance de una descarga.

    Attributes:
        job (DownloadJob): Descarga en curso (``done_bytes`` y ``total_bytes`` actualizados).
        current_file (str): Archivo que se está descargando.
        bytes_per_second (float): Velocidad media reciente.
        eta_seconds (float | None): Tiempo restante estimado; ``None`` si aún no se sabe.
    """

    job: DownloadJob
    current_file: str
    bytes_per_second: float
    eta_seconds: float | None = None


@dataclass(frozen=True)
class TransferRetrying:
    """Se cortó una transferencia y se reintentará automáticamente.

    Attributes:
        row_id (str): Fila de la transferencia (descarga o subida).
        attempt (int): Número de reintento (desde 1).
        max_attempts (int): Reintentos máximos.
        reason (str): Causa del corte, para el usuario.
    """

    row_id: str
    attempt: int
    max_attempts: int
    reason: str


@dataclass(frozen=True)
class DownloadFinished:
    """Terminó una descarga (con éxito, error o cancelación).

    Attributes:
        job (DownloadJob): Descarga terminada.
        result (DownloadResult): Resultado.
    """

    job: DownloadJob
    result: DownloadResult


@dataclass(frozen=True)
class DownloadQueueFinished:
    """Terminó toda la cola de descargas.

    Attributes:
        cancelled (bool): ``True`` si terminó por una cancelación del usuario.
    """

    cancelled: bool


RemoteEvent = (
    RemoteConnected
    | RemoteDisconnected
    | RemoteListing
    | RemoteError
    | PairingCodeRequired
    | StorageUpdated
    | FtpReady
    | FtpLoginRefused
    | DownloadStarted
    | DownloadProgress
    | TransferRetrying
    | DownloadFinished
    | DownloadQueueFinished
)
