"""Acumula el avance de una descarga y lo publica con una frecuencia limitada."""
from __future__ import annotations

import time
from collections.abc import Callable

from ffpfsc_converter.config import PROGRESS_INTERVAL_SECONDS
from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.remote import DownloadJob
from ffpfsc_converter.domain.remote_events import DownloadProgress
from ffpfsc_converter.timing import EtaEstimator, SpeedAverage


class ProgressMeter:
    """Suma bytes a ``job.done_bytes`` y publica ``DownloadProgress`` cada cierto tiempo.

    Publicar en cada bloque saturaría la interfaz; se publica como máximo una
    vez por ``interval`` segundos, con la velocidad de ese intervalo.
    """

    def __init__(
        self,
        job: DownloadJob,
        emit: EventSink,
        interval: float = PROGRESS_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Prepara el medidor para una descarga.

        Args:
            job (DownloadJob): Descarga cuyo avance se mide.
            emit (EventSink): Destino de los eventos.
            interval (float): Segundos mínimos entre dos publicaciones.
            clock (Callable[[], float]): Reloj monotónico; los tests lo sustituyen.
        """
        self._job = job
        self._emit = emit
        self._interval = interval
        self._clock = clock
        self._last_time = clock()
        self._last_bytes = job.done_bytes
        self._skipped = job.done_bytes
        self._speed = 0.0
        self._average = SpeedAverage()
        self._eta = EtaEstimator(clock)

    def skip(self, size: int) -> None:
        """Cuenta bytes que ya estaban en el equipo, sin afectar la velocidad.

        Args:
            size (int): Bytes que no hace falta descargar.
        """
        self._job.done_bytes += size
        self._last_bytes += size
        self._skipped += size

    def rewind(self, size: int) -> None:
        """Descuenta bytes que se habían contado como ya descargados y se descartaron.

        Args:
            size (int): Bytes que hay que volver a descargar.
        """
        self._job.done_bytes -= size
        self._last_bytes -= size
        self._skipped -= size

    def advance(self, size: int, current_file: str) -> None:
        """Suma bytes recibidos y publica el avance si ya pasó el intervalo.

        Args:
            size (int): Bytes recibidos en este bloque.
            current_file (str): Nombre del archivo que se está descargando.
        """
        self._job.done_bytes += size
        now = self._clock()
        elapsed = now - self._last_time
        if elapsed >= self._interval:
            self._speed = self._average.add((self._job.done_bytes - self._last_bytes) / elapsed)
            self._last_time, self._last_bytes = now, self._job.done_bytes
            self.publish(current_file)

    def publish(self, current_file: str) -> None:
        """Publica el avance actual sin esperar al intervalo.

        Args:
            current_file (str): Nombre del archivo que se está descargando.
        """
        done, total = self._job.done_bytes, self._job.total_bytes
        eta = self._eta.update(done - self._skipped, total - done)
        self._emit(DownloadProgress(self._job, current_file, self._speed, eta))
