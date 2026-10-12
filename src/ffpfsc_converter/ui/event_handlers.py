"""Traduce los eventos de los servicios en cambios de la vista.

Se ejecuta siempre en el hilo de la interfaz (lo invoca el bucle de sondeo de
:class:`~ffpfsc_converter.ui.app.MainWindow`).
"""
from __future__ import annotations

from collections.abc import Callable

from ffpfsc_converter.config import PRESETS
from ffpfsc_converter.domain.events import (
    Event,
    JobEstimateReady,
    JobFinished,
    JobInfoReady,
    JobProgress,
    JobSizeReady,
    JobStarted,
    LogMessage,
    QueueFinished,
)
from ffpfsc_converter.domain.models import ConversionJob, OutputFormat
from ffpfsc_converter.ui import job_presenters as jp
from ffpfsc_converter.ui import presenters
from ffpfsc_converter.ui.main_view import MainView


class ViewUpdater:
    """Aplica cada evento recibido sobre la vista principal."""

    def __init__(self, view: MainView) -> None:
        """Registra el manejador de cada tipo de evento.

        Args:
            view (MainView): Vista a actualizar.
        """
        self._view = view
        self._handlers: dict[type, Callable] = {
            JobInfoReady: self._on_job_info,
            JobSizeReady: self._on_job_size,
            JobEstimateReady: self._on_job_estimate,
            JobStarted: self._on_job_started,
            JobProgress: self._on_job_progress,
            LogMessage: self._on_log_message,
            JobFinished: self._on_job_finished,
            QueueFinished: self._on_queue_finished,
        }

    def handle(self, event: Event) -> None:
        """Despacha un evento a su manejador.

        Args:
            event (Event): Evento publicado por un servicio.

        Raises:
            KeyError: Si el tipo de evento no tiene manejador registrado.
        """
        self._handlers[type(event)](event)

    def _size_lines(self, job: ConversionJob) -> jp.SizeText:
        """Genera los tamaños de una fila con el modo y el rendimiento elegidos en la vista.

        Args:
            job (ConversionJob): Trabajo a mostrar.

        Returns:
            jp.SizeText: Tamaño original, estimado y ahorro.
        """
        options = self._view.options
        return jp.size_lines(job, options.selected_preset().level, options.is_performance(),
                             options.output_format() is OutputFormat.LZ4)

    def _on_job_info(self, event: JobInfoReady) -> None:
        """Muestra el nombre del juego y su Title ID y versión.

        Args:
            event (JobInfoReady): Evento con el trabajo actualizado.
        """
        job = event.job
        meta = jp.game_meta(job.info, presenters.source_display_name(job))
        self._view.table.set_info(job.id, jp.game_title(job.info), meta)

    def _on_job_size(self, event: JobSizeReady) -> None:
        """Muestra el tamaño original del juego.

        Args:
            event (JobSizeReady): Evento con el trabajo actualizado.
        """
        self._view.table.set_sizes(event.job.id, self._size_lines(event.job))

    def _on_job_estimate(self, event: JobEstimateReady) -> None:
        """Muestra el peso estimado del modo actual y registra todos los modos.

        Args:
            event (JobEstimateReady): Evento con el trabajo actualizado.
        """
        job = event.job
        self._view.table.set_sizes(job.id, self._size_lines(job))
        self._view.write_log(presenters.estimates_summary(job, PRESETS))

    def _on_job_started(self, event: JobStarted) -> None:
        """Marca el trabajo como en curso y registra el comando.

        Args:
            event (JobStarted): Evento con el trabajo y el comando.
        """
        name = event.job.source.name
        self._view.table.set_status(event.job.id, "run", presenters.RUNNING_TEXT, "", 0)
        self._view.write_log(f"\n=== {name} ===\n$ {event.command}")
        self._view.set_status(f"Convirtiendo {name}…")

    def _on_job_progress(self, event: JobProgress) -> None:
        """Actualiza la píldora, la barra y el tiempo restante de la fila.

        Args:
            event (JobProgress): Evento con el progreso de MkPFS.
        """
        kind, label, detail = jp.progress_status(event.progress, event.eta_seconds)
        self._view.table.set_status(event.job.id, kind, label, detail, event.progress.percent)
        self._view.set_status(f"{event.job.source.name}: {label}")

    def _on_log_message(self, event: LogMessage) -> None:
        """Agrega una línea al registro.

        Args:
            event (LogMessage): Evento con el texto.
        """
        self._view.write_log(event.text)

    def _on_job_finished(self, event: JobFinished) -> None:
        """Muestra el resultado del trabajo.

        Args:
            event (JobFinished): Evento con el trabajo y su resultado.
        """
        kind, label, detail = jp.result_status(event.job, event.result)
        self._view.table.set_status(event.job.id, kind, label, detail)

    def _on_queue_finished(self, event: QueueFinished) -> None:
        """Rehabilita los botones y muestra cómo terminó la cola.

        Args:
            event (QueueFinished): Evento de fin de cola.
        """
        self._view.set_running(False)
        self._view.set_status("Cancelado." if event.cancelled else "Terminado.")
