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
from ffpfsc_converter.ui import job_table, presenters
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

    def _on_job_info(self, event: JobInfoReady) -> None:
        """Muestra el nombre del juego.

        Args:
            event (JobInfoReady): Evento con el trabajo actualizado.
        """
        text = presenters.game_info_text(event.job.info)
        self._view.table.set_cell(event.job.id, job_table.TITLE, text)

    def _on_job_size(self, event: JobSizeReady) -> None:
        """Muestra el tamaño original del juego.

        Args:
            event (JobSizeReady): Evento con el trabajo actualizado.
        """
        text = presenters.format_size(event.job.size)
        self._view.table.set_cell(event.job.id, job_table.SIZE, text)

    def _on_job_estimate(self, event: JobEstimateReady) -> None:
        """Muestra el peso estimado del modo actual y registra todos los modos.

        Args:
            event (JobEstimateReady): Evento con el trabajo actualizado.
        """
        job = event.job
        level = self._view.options.selected_preset().level
        self._view.table.set_cell(job.id, job_table.ESTIMATE, presenters.estimate_text(job, level))
        self._view.write_log(presenters.estimates_summary(job, PRESETS))

    def _on_job_started(self, event: JobStarted) -> None:
        """Marca el trabajo como en curso y registra el comando.

        Args:
            event (JobStarted): Evento con el trabajo y el comando.
        """
        name = event.job.source.name
        self._view.table.set_cell(event.job.id, job_table.STATUS, presenters.RUNNING_TEXT)
        self._view.set_progress(0)
        self._view.write_log(f"\n=== {name} ===\n$ {event.command}")
        self._view.set_status(f"Convirtiendo {name}…")

    def _on_job_progress(self, event: JobProgress) -> None:
        """Actualiza la barra, el estado del trabajo y la línea de estado.

        Args:
            event (JobProgress): Evento con el progreso de MkPFS.
        """
        text = presenters.progress_text(event.progress, event.eta_seconds)
        self._view.set_progress(event.progress.percent)
        self._view.table.set_cell(event.job.id, job_table.STATUS, text)
        self._view.set_status(f"{event.job.source.name}: {text}")

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
        text = presenters.result_text(event.job, event.result)
        self._view.table.set_cell(event.job.id, job_table.STATUS, text)
        if event.result.succeeded:
            self._view.set_progress(100)

    def _on_queue_finished(self, event: QueueFinished) -> None:
        """Rehabilita los botones y muestra cómo terminó la cola.

        Args:
            event (QueueFinished): Evento de fin de cola.
        """
        self._view.set_running(False)
        self._view.set_status("Cancelado." if event.cancelled else "Terminado.")
