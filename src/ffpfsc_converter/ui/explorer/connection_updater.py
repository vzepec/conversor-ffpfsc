"""Aplica los eventos de conexión con la PS5: inicio del FTP, emparejamiento,
conexión, errores y reconexión automática tras un corte."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ffpfsc_converter.config import RECONNECT_ATTEMPTS, RECONNECT_DELAY_MS
from ffpfsc_converter.domain.remote_events import (
    FtpLoginRefused,
    FtpReady,
    FtpRestoreFailed,
    PairingCodeRequired,
    RemoteConnected,
    RemoteDisconnected,
    RemoteError,
)
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.explorer.pairing_dialog import PairingDialog

if TYPE_CHECKING:  # evita la importación circular con el controlador
    from ffpfsc_converter.ui.explorer.controller import ExplorerController


class ConnectionUpdater:
    """Manejadores de los eventos de conexión.

    Attributes:
        handlers (dict[type, Callable]): Tipo de evento → manejador.
    """

    def __init__(self, controller: ExplorerController) -> None:
        """Registra los manejadores.

        Args:
            controller (ExplorerController): Controlador de la vista PS5.
        """
        self._ctl, self._view = controller, controller.view
        self.handlers: dict[type, Callable] = {
            FtpReady: self._on_ftp_ready,
            FtpRestoreFailed: self._on_restore_failed,
            FtpLoginRefused: self._on_login_refused,
            PairingCodeRequired: self._on_pairing_code,
            RemoteConnected: self._on_connected,
            RemoteDisconnected: self._on_disconnected,
            RemoteError: self._on_error,
        }

    def _on_ftp_ready(self, event: FtpReady) -> None:
        """Conecta el explorador al FTP ya activo (en la carpeta abierta si se reconecta).

        Args:
            event (FtpReady): FTP listo.
        """
        if self._ctl.target is not None:  # vuelve a solo lectura tras escribir: sigue conectada
            self._view.connection.set_state(True, "Volviendo el FTP a solo lectura…", busy=True)
        else:
            verb = "FTP iniciado" if event.started else "FTP activo"
            self._view.connection.set_state(False, f"{verb}; abriendo…", busy=True)
        keep_path = self._ctl.target is not None or self._ctl.reconnects > 0
        self._ctl.browser.connect(event.target, start_path=self._ctl.path if keep_path else None)

    def _on_restore_failed(self, _event: FtpRestoreFailed) -> None:
        """Recupera la vista si el FTP no volvió a solo lectura tras escribir.

        Se trata como un corte: se reinicia el FTP (en solo lectura) y se vuelve a
        la carpeta abierta; así la navegación nunca queda en pausa para siempre.

        Args:
            _event (FtpRestoreFailed): Aviso del servicio.
        """
        self._ctl.target = None
        self._ctl.needs_restart = True
        self._view.set_connected(False)
        self._schedule_reconnect()

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
        """Pide el código que muestra la PS5 (en una conexión automática, no molesta).

        Args:
            event (PairingCodeRequired): Solicitud de código.
        """
        if self._ctl.quiet:
            self._ctl.launcher.provide_code(None)
            return
        self._view.connection.set_state(False, "Esperando el código de emparejamiento…", True)
        code = PairingDialog(self._view, self._ctl.theme, event.console_name).ask()
        self._ctl.launcher.provide_code(code)

    def _on_connected(self, event: RemoteConnected) -> None:
        """Marca la conexión como activa y ejecuta lo que esperaba la conexión.

        Args:
            event (RemoteConnected): Conexión establecida.
        """
        self._ctl.target = event.target
        self._ctl.ftp_restarted = False
        self._ctl.quiet, self._ctl.user_disconnected, self._ctl.reconnects = False, False, 0
        self._ctl.needs_restart = False
        self._view.set_connected(True)
        self._view.set_browsing_enabled(True)
        self._ctl.refresh_storage()
        pending, self._ctl.pending_on_connect = self._ctl.pending_on_connect, []
        for action in pending:
            action()

    def _on_disconnected(self, _event: RemoteDisconnected) -> None:
        """Vacía el explorador y, si el corte no lo pidió el usuario, intenta reconectar.

        Args:
            _event (RemoteDisconnected): Desconexión.
        """
        self._ctl.target = None
        self._view.remote.clear()
        self._view.set_connected(False)
        self._view.connection.set_state(False, "Sin conexión.")
        if not self._ctl.user_disconnected:
            self._schedule_reconnect()

    def _on_error(self, event: RemoteError) -> None:
        """Muestra el error (salvo en una conexión automática) y restablece el estado.

        Args:
            event (RemoteError): Error a mostrar.
        """
        connected = self._ctl.browser.is_connected
        self._view.connection.set_state(connected, "Conectado." if connected else "Sin conexión.")
        if not self._ctl.quiet:
            dialogs.show_error(event.message)
            return
        self._ctl.quiet = False
        if not connected and self._ctl.reconnects > 0:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        """Programa otro intento de reconexión, hasta ``RECONNECT_ATTEMPTS``."""
        if self._ctl.reconnects >= RECONNECT_ATTEMPTS:
            self._ctl.reconnects = 0
            return
        self._ctl.reconnects += 1
        self._view.connection.set_state(
            False, f"Reconectando ({self._ctl.reconnects} de {RECONNECT_ATTEMPTS})…")
        self._view.after(RECONNECT_DELAY_MS, self._ctl.auto_connect)
