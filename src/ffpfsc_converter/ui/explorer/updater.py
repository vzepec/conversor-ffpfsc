"""Aplica los eventos del explorador de la PS5 sobre la vista."""
from __future__ import annotations

from collections.abc import Callable

from ffpfsc_converter.domain.remote_events import (
    DownloadFinished,
    DownloadProgress,
    DownloadQueueFinished,
    DownloadStarted,
    FtpLoginRefused,
    FtpReady,
    PairingCodeRequired,
    RemoteConnected,
    RemoteDisconnected,
    RemoteError,
    RemoteListing,
    StorageUpdated,
    TransferRetrying,
)
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.explorer import presenters
from ffpfsc_converter.ui.explorer.changes_updater import ChangesUpdater
from ffpfsc_converter.ui.explorer.controller import ExplorerController
from ffpfsc_converter.ui.explorer.pairing_dialog import PairingDialog


class ExplorerUpdater:
    """Despacha los eventos remotos a sus manejadores (en el hilo de la interfaz)."""

    def __init__(self, controller: ExplorerController) -> None:
        """Registra los manejadores.

        Args:
            controller (ExplorerController): Controlador de la vista.
        """
        self._ctl = controller
        self._view = controller.view
        self._handlers: dict[type, Callable] = {
            FtpReady: self._on_ftp_ready,
            FtpLoginRefused: self._on_login_refused,
            PairingCodeRequired: self._on_pairing_code,
            RemoteConnected: self._on_connected,
            RemoteDisconnected: self._on_disconnected,
            RemoteListing: self._on_listing,
            StorageUpdated: self._on_storage,
            RemoteError: self._on_error,
            DownloadStarted: self._on_download_started,
            DownloadProgress: self._on_download_progress,
            DownloadFinished: self._on_download_finished,
            DownloadQueueFinished: self._on_queue_finished,
            TransferRetrying: self._on_retrying,
            **ChangesUpdater(controller).handlers,
        }

    def handles(self, event: object) -> bool:
        """Indica si el evento pertenece a la vista PS5.

        Args:
            event (object): Evento recibido.

        Returns:
            bool: ``True`` si hay un manejador para su tipo.
        """
        return type(event) in self._handlers

    def handle(self, event: object) -> None:
        """Ejecuta el manejador del evento.

        Args:
            event (object): Evento de la vista PS5.
        """
        self._handlers[type(event)](event)

    def _on_ftp_ready(self, event: FtpReady) -> None:
        """Conecta el explorador al FTP ya activo.

        Args:
            event (FtpReady): FTP listo.
        """
        verb = "FTP iniciado" if event.started else "FTP activo"
        self._view.connection.set_state(False, f"{verb}; abriendo…", busy=True)
        start = self._ctl.path if self._ctl.target is not None else None
        self._ctl.browser.connect(event.target, start_path=start)

    def _on_login_refused(self, event: FtpLoginRefused) -> None:
        """Reinicia el FTP con credenciales nuevas (lo había iniciado otro programa).

        Args:
            event (FtpLoginRefused): Rechazo del inicio de sesión.
        """
        if self._ctl.ftp_restarted:
            self._view.connection.set_state(False, "Sin conexión.")
            dialogs.show_error("El FTP de la PS5 rechazó las credenciales "
                               "incluso tras reiniciarlo.")
            return
        self._ctl.ftp_restarted = True
        self._view.connection.set_state(False, "Reiniciando el FTP de la PS5…", busy=True)
        self._ctl.launcher.connect(event.target.host, event.target.port, restart=True)

    def _on_pairing_code(self, event: PairingCodeRequired) -> None:
        """Pide al usuario el código que muestra la PS5.

        Args:
            event (PairingCodeRequired): Solicitud de código.
        """
        self._view.connection.set_state(False, "Esperando el código de emparejamiento…", True)
        code = PairingDialog(self._view, self._ctl.theme, event.console_name).ask()
        self._ctl.launcher.provide_code(code)

    def _on_connected(self, event: RemoteConnected) -> None:
        """Marca la conexión como activa.

        Args:
            event (RemoteConnected): Conexión establecida.
        """
        self._ctl.target = event.target
        self._ctl.ftp_restarted = False
        self._view.set_browsing_enabled(True)
        self._ctl.refresh_storage()
        pending, self._ctl.pending_on_connect = self._ctl.pending_on_connect, []
        for action in pending:
            action()

    def _on_disconnected(self, _event: RemoteDisconnected) -> None:
        """Vacía el explorador al perder la conexión.

        Args:
            _event (RemoteDisconnected): Desconexión.
        """
        self._ctl.target = None
        self._view.remote.clear()
        self._view.set_browsing_enabled(False)
        self._view.set_storage((), "")
        self._view.connection.set_state(False, "Sin conexión.")

    def _on_listing(self, event: RemoteListing) -> None:
        """Muestra el contenido de la carpeta abierta.

        Args:
            event (RemoteListing): Carpeta listada.
        """
        self._ctl.path, self._ctl.entries = event.path, event.entries
        self._view.set_path(event.path)
        self._view.remote.show(event.entries)
        target = self._ctl.target
        if target is not None:
            text = presenters.connection_text(target.host, target.port, event.path)
            self._view.connection.set_state(True, text)

    def _on_storage(self, event: StorageUpdated) -> None:
        """Muestra el espacio libre de las unidades (si sigue habiendo conexión).

        Args:
            event (StorageUpdated): Resultado de la consulta.
        """
        if self._ctl.target is not None:
            self._view.set_storage(event.volumes, event.error)

    def _on_error(self, event: RemoteError) -> None:
        """Muestra el error y restablece el estado de la barra de conexión.

        Args:
            event (RemoteError): Error a mostrar.
        """
        connected = self._ctl.browser.is_connected
        self._view.connection.set_state(connected, "Conectado." if connected else "Sin conexión.")
        dialogs.show_error(event.message)

    def _on_download_started(self, event: DownloadStarted) -> None:
        """Marca la descarga como iniciada.

        Args:
            event (DownloadStarted): Descarga iniciada.
        """
        self._view.transfers.update_job(event.job, 0.0, "…")

    def _on_download_progress(self, event: DownloadProgress) -> None:
        """Actualiza el progreso de la descarga.

        Args:
            event (DownloadProgress): Avance.
        """
        self._view.transfers.update_job(event.job, event.bytes_per_second, event.current_file,
                                        event.eta_seconds)

    def _on_download_finished(self, event: DownloadFinished) -> None:
        """Muestra el resultado de la descarga.

        Args:
            event (DownloadFinished): Descarga terminada.
        """
        self._view.transfers.finish_job(event.job, event.result)
        self._ctl.retry.download_finished(event.job, event.result)

    def _on_retrying(self, event: TransferRetrying) -> None:
        """Avisa en la fila que se reintentará la transferencia.

        Args:
            event (TransferRetrying): Reintento automático en curso.
        """
        self._view.transfers.set_state(
            event.row_id, "warn", f"Reintentando ({event.attempt} de {event.max_attempts})…",
            event.reason, active=True)
        listener = self._ctl.upload_listeners.get(event.row_id)
        if listener is not None:
            listener(event)

    def _on_queue_finished(self, _event: DownloadQueueFinished) -> None:
        """Deshabilita "Cancelar" al terminar la cola.

        Args:
            _event (DownloadQueueFinished): Fin de la cola.
        """
        self._view.transfers.set_running(False)
