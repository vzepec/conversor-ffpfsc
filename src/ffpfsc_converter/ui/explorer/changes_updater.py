"""Aplica en la pestaña PS5 los eventos de borrado, subida y del pipeline."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ffpfsc_converter.domain.pipeline_events import (
    PipelineConfirmRequired,
    PipelineFinished,
    PipelineOptionsRequired,
    PipelineProgress,
    PipelineStageChanged,
    RemoteDeleted,
    RemoteDeleteProgress,
    UploadFinished,
    UploadProgress,
)
from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.explorer import presenters
from ffpfsc_converter.ui.explorer.compress_dialog import CompressDialog

if TYPE_CHECKING:  # evita la importación circular con el controlador
    from ffpfsc_converter.ui.explorer.controller import ExplorerController


class ChangesUpdater:
    """Manejadores de los eventos de escritura en la PS5.

    Attributes:
        handlers (dict[type, Callable]): Tipo de evento → manejador.
    """

    def __init__(self, controller: ExplorerController) -> None:
        """Registra los manejadores.

        Args:
            controller (ExplorerController): Controlador de la pestaña.
        """
        self._ctl = controller
        self.handlers: dict[type, Callable] = {
            RemoteDeleteProgress: self._on_delete_progress,
            RemoteDeleted: self._on_deleted,
            UploadProgress: self._on_upload_progress,
            UploadFinished: self._on_upload_finished,
            PipelineStageChanged: self._on_stage,
            PipelineProgress: self._on_progress,
            PipelineOptionsRequired: self._on_options,
            PipelineConfirmRequired: self._on_confirm,
            PipelineFinished: self._on_finished,
        }

    def _on_delete_progress(self, event: RemoteDeleteProgress) -> None:
        """Muestra el avance del borrado.

        Args:
            event (RemoteDeleteProgress): Avance.
        """
        total = f" ({event.files_done} de {event.files_total})" if event.files_total else ""
        self._ctl.view.connection.set_state(True, f"Eliminando {event.path}{total}…", busy=True)

    def _on_deleted(self, event: RemoteDeleted) -> None:
        """Refresca la carpeta tras borrar.

        Args:
            event (RemoteDeleted): Rutas borradas.
        """
        self._ctl.view.connection.set_state(True, f"Eliminado: {len(event.paths)} elemento(s).")
        self._ctl.refresh()

    def _on_upload_progress(self, event: UploadProgress) -> None:
        """Actualiza la fila de la subida.

        Args:
            event (UploadProgress): Avance.
        """
        self._ctl.view.transfers.set_progress(
            event.upload_id, event.done, event.total,
            presenters.speed_text(event.bytes_per_second), format_eta(event.eta_seconds))
        self._notify(event.upload_id, event)

    def _on_upload_finished(self, event: UploadFinished) -> None:
        """Muestra el resultado de la subida.

        Args:
            event (UploadFinished): Resultado.
        """
        if event.succeeded:
            self._ctl.view.transfers.set_state(event.upload_id, "ok", "✓ Subido", event.message)
        else:
            self._ctl.view.transfers.set_state(event.upload_id, "bad", "Error", event.message)
        self._ctl.retry.upload_finished(event.upload_id, event.succeeded)
        if event.succeeded:
            self._ctl.refresh_storage()
        self._notify(event.upload_id, event)

    def _notify(self, upload_id: str, event: object) -> None:
        """Reenvía el evento a quien siga esa subida (por ejemplo, la pestaña Convertir).

        Args:
            upload_id (str): Fila de la subida.
            event (object): Evento de progreso o de fin.
        """
        listener = self._ctl.upload_listeners.get(upload_id)
        if listener is not None:
            listener(event)

    def _on_stage(self, event: PipelineStageChanged) -> None:
        """Avanza la ventana del pipeline a la etapa nueva.

        Args:
            event (PipelineStageChanged): Etapa nueva.
        """
        if self._ctl.modify.window is not None:
            self._ctl.modify.window.set_stage(event.stage, event.detail)

    def _on_progress(self, event: PipelineProgress) -> None:
        """Actualiza la barra de la ventana del pipeline.

        Args:
            event (PipelineProgress): Avance.
        """
        if self._ctl.modify.window is not None:
            self._ctl.modify.window.set_progress(event.percent, event.detail, event.eta_seconds)

    def _on_options(self, event: PipelineOptionsRequired) -> None:
        """Muestra la ventana de compresión y entrega la elección al pipeline.

        Args:
            event (PipelineOptionsRequired): Juego analizado y plan de reemplazo.
        """
        choice = CompressDialog(self._ctl.view, self._ctl.theme, event.job, event.plan).ask()
        self._ctl.modify.pipeline.answer(choice)

    def _on_confirm(self, event: PipelineConfirmRequired) -> None:
        """Pide la confirmación adicional y la entrega al pipeline.

        Args:
            event (PipelineConfirmRequired): Pregunta.
        """
        self._ctl.modify.pipeline.answer(dialogs.confirm_warning(event.message))

    def _on_finished(self, event: PipelineFinished) -> None:
        """Muestra el resultado y refresca la carpeta.

        Args:
            event (PipelineFinished): Resultado.
        """
        self._ctl.refresh_storage()
        window = self._ctl.modify.window
        if window is not None and window.winfo_exists():
            window.finish(event.result)
        elif not event.result.succeeded:
            dialogs.show_error(event.result.message)
