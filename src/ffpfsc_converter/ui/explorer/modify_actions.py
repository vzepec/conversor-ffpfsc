"""Acciones que modifican la PS5: eliminar, subir archivos y comprimir y reemplazar."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ffpfsc_converter.config import PIPELINE_WORK_DIR_NAME
from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.services.console_access import ConsoleAccess
from ffpfsc_converter.services.pipeline.plan import is_convertible
from ffpfsc_converter.services.pipeline.runner import Ps5ConversionPipeline
from ffpfsc_converter.services.remote_changes import RemoteChanges
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.explorer import presenters
from ffpfsc_converter.ui.explorer.pipeline_tracker import PipelineTracker

if TYPE_CHECKING:  # evita la importación circular con el controlador
    from ffpfsc_converter.ui.explorer.controller import ExplorerController


class ModifyActions:
    """Coordina las operaciones de escritura en la PS5 desde la vista.

    Attributes:
        changes (RemoteChanges): Eliminar y subir archivos.
        pipeline (Ps5ConversionPipeline): Comprimir y reemplazar.
        tracker (PipelineTracker | None): Fila del pipeline en el panel de transferencias.
    """

    def __init__(self, controller: ExplorerController, emit: EventSink,
                 access: ConsoleAccess) -> None:
        """Crea los servicios de escritura.

        Args:
            controller (ExplorerController): Controlador de la vista.
            emit (EventSink): Cola de eventos de la ventana principal.
            access (ConsoleAccess): Acceso AVA1 a la consola.
        """
        self._ctl = controller
        self.changes = RemoteChanges(emit, access)
        self.pipeline = Ps5ConversionPipeline(emit, access)
        self.tracker: PipelineTracker | None = None

    @property
    def busy(self) -> bool:
        """Indica si hay una operación de escritura en curso.

        Returns:
            bool: ``True`` mientras se elimina, se sube o corre el pipeline.
        """
        return self.changes.busy or self.pipeline.busy

    def delete_selected(self) -> None:
        """Elimina en la PS5 los elementos seleccionados, tras confirmar."""
        entries = self._ctl.view.remote.selected_entries()
        if not entries or not self._ready():
            dialogs.show_info("Selecciona uno o más archivos o carpetas de la PS5.")
            return
        paths = [e.path for e in entries]
        if not dialogs.confirm_remote_delete(presenters.delete_summary(paths)):
            return
        assert self._ctl.target is not None
        self._ctl.view.connection.set_state(True, "Eliminando en la PS5…", busy=True)
        self.changes.delete(self._ctl.target.host, paths)

    def upload_files(self) -> None:
        """Sube archivos de este equipo a la carpeta remota abierta."""
        if not self._ready():
            return
        files = dialogs.ask_upload_files()
        if files:
            self.upload_paths(files, self._ctl.path)

    def upload_paths(self, files: list[Path], remote_dir: str) -> list[str]:
        """Sube archivos concretos a una carpeta de la PS5 (con filas en el panel).

        Args:
            files (list[Path]): Archivos locales.
            remote_dir (str): Carpeta remota de destino.

        Returns:
            list[str]: Filas de las subidas; vacía si no se pudo iniciar.
        """
        if not self._ready():
            return []
        assert self._ctl.target is not None
        target = self._ctl.target
        ids = self.changes.upload(target.host, target.port, files, remote_dir)
        for upload_id, local in zip(ids, files, strict=True):
            self._ctl.view.transfers.add_row(upload_id, local.name, "upload")
            self._ctl.retry.register_upload(upload_id, local, remote_dir)
        self._ctl.view.set_browsing_enabled(False)
        self._ctl.view.connection.set_state(True, f"Subiendo a {remote_dir}…", busy=True)
        return ids

    def convert_selected(self) -> None:
        """Inicia "comprimir y reemplazar" para la carpeta o imagen seleccionada."""
        entries = self._ctl.view.remote.selected_entries()
        if len(entries) != 1 or not is_convertible(entries[0]):
            dialogs.show_info("Selecciona UNA carpeta de juego o una imagen .exfat / .ffpkg.")
            return
        if not self._ready() or (self._ctl.download_dir is None
                                 and not self._ctl.choose_destination()):
            return
        assert self._ctl.target is not None and self._ctl.download_dir is not None
        entry = entries[0]
        siblings = [e.name for e in self._ctl.entries]
        self.tracker = PipelineTracker(self._ctl.view.transfers, entry.name,
                                       (self.pipeline.cancel, self.retry_pipeline))
        self.pipeline.start(entry, self._ctl.target, siblings,
                            self._ctl.download_dir / PIPELINE_WORK_DIR_NAME)

    def retry_pipeline(self) -> None:
        """Reintenta "comprimir y reemplazar" desde donde quedó (sin volver a comprimir)."""
        if self.pipeline.last is None or not self._ready():
            return
        assert self._ctl.target is not None
        if self.tracker is not None:
            self.tracker.restart()
        self.pipeline.retry(self._ctl.target)

    def _ready(self) -> bool:
        """Comprueba que haya conexión y ninguna otra operación en curso.

        Returns:
            bool: ``True`` si se puede iniciar una operación nueva.
        """
        if self._ctl.target is None:
            dialogs.show_error("No hay conexión con la PS5.")
            return False
        if self.busy or self._ctl.downloads.is_running:
            dialogs.show_info("Espera a que termine la operación en curso.")
            return False
        return True
