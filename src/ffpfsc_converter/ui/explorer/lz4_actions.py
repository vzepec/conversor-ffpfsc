"""Coordina la compresión LZ4 en la PS5 (exfat2ampr) con la vista: diálogos, fila y estado."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ffpfsc_converter.domain.lz4 import Lz4Check, Lz4JobState, Lz4Plan, Lz4Status
from ffpfsc_converter.domain.lz4_events import Lz4PairingRequired
from ffpfsc_converter.services.lz4_deps import Lz4Deps, Lz4Sink
from ffpfsc_converter.services.lz4_remote import Lz4Remote
from ffpfsc_converter.services.pipeline.plan import is_convertible
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.explorer import presenters
from ffpfsc_converter.ui.explorer.elf_dialog import ElfRequiredDialog
from ffpfsc_converter.ui.explorer.lz4_dialog import Lz4Dialog
from ffpfsc_converter.ui.explorer.lz4_presenters import (
    LZ4_BUSY_TEXT,
    REPAIR_TEXT,
    SELECT_ONE_TEXT,
    rejection_text,
)
from ffpfsc_converter.ui.explorer.lz4_status_presenters import job_name
from ffpfsc_converter.ui.explorer.lz4_target_presenters import pairing_text, remove_confirmation
from ffpfsc_converter.ui.explorer.lz4_tracker import Lz4RowActions, Lz4Tracker
from ffpfsc_converter.ui.explorer.pairing_dialog import PairingDialog

if TYPE_CHECKING:  # evita la importación circular con el controlador
    from ffpfsc_converter.ui.explorer.controller import ExplorerController

_ENGINE_NAME = "exfat2ampr"
_PREPARING_TEXT = "Preparando la compresión LZ4 en la PS5…"
_PAIRING_TEXT = "Emparejando con exfat2ampr…"


class Lz4Actions:
    """Pide, confirma y sigue conversiones LZ4 de exfat2ampr desde la vista PS5.

    Attributes:
        remote (Lz4Remote): Servicio que habla con exfat2ampr.
        tracker (Lz4Tracker | None): Fila de la última conversión, o ``None``.
    """

    def __init__(self, controller: ExplorerController, emit: Lz4Sink,
                 deps: Lz4Deps | None = None) -> None:
        """Crea el servicio sin conectarse a la PS5.

        Args:
            controller (ExplorerController): Controlador de la vista.
            emit (Lz4Sink): Cola de eventos de la ventana principal.
            deps (Lz4Deps | None): Dependencias del servicio; ``None`` usa las reales.
        """
        self._ctl = controller
        self._deps = deps or Lz4Deps()
        self.remote = Lz4Remote(emit, self._deps)
        self.tracker: Lz4Tracker | None = None

    @property
    def busy(self) -> bool:
        """Indica si se está iniciando o siguiendo una conversión.

        Returns:
            bool: ``True`` mientras exfat2ampr trabaja en algo pedido o visto por la app.
        """
        return self.remote.busy

    def compress_selected(self) -> None:
        """Pide a exfat2ampr que analice la carpeta o imagen seleccionada."""
        entries = self._ctl.view.remote.selected_entries()
        if len(entries) != 1 or not is_convertible(entries[0]):
            dialogs.show_info(SELECT_ONE_TEXT)
            return
        if self._ctl.target is None:
            dialogs.show_error("No hay conexión con la PS5.")
            return
        if self.busy or (self.tracker is not None and self.tracker.is_active):
            dialogs.show_info(LZ4_BUSY_TEXT)
            return
        self.show_status(_PREPARING_TEXT)
        self.remote.prepare(self._ctl.target.host, entries[0].path)

    def ask_elf(self, host: str, entry_path: str) -> None:
        """Explica que falta ``exfat2ampr.elf``, lo pide, lo recuerda y vuelve a intentar.

        Args:
            host (str): Dirección de la PS5.
            entry_path (str): Juego que se quería convertir.
        """
        self.restore_status()
        if not ElfRequiredDialog(self._ctl.view, self._ctl.theme).ask():
            return
        elf = dialogs.ask_elf_file()
        if elf is None:
            return
        self._deps.settings.save_elf_path(elf)
        self.show_status(_PREPARING_TEXT)
        self.remote.prepare(host, entry_path)

    def ask_pairing(self, event: Lz4PairingRequired) -> None:
        """Pide el código de exfat2ampr y empareja la app.

        Args:
            event (Lz4PairingRequired): Solicitud (indica si el código anterior falló).
        """
        self.restore_status()
        if self.tracker is not None and self.tracker.is_active:
            self.tracker.fail(REPAIR_TEXT)
        if not event.entry_path:
            dialogs.show_info(REPAIR_TEXT)
            return
        message = pairing_text(event.host, event.retry)
        code = PairingDialog(self._ctl.view, self._ctl.theme, _ENGINE_NAME, message).ask()
        if not code:
            return
        self.show_status(_PAIRING_TEXT)
        self.remote.pair(event.host, code, event.entry_path)

    def review(self, host: str, plan: Lz4Plan) -> None:
        """Muestra la ventana de compresión y, si se confirma, inicia la conversión.

        Args:
            host (str): Dirección de la PS5.
            plan (Lz4Plan): Juego analizado por exfat2ampr.
        """
        self.restore_status()
        request = Lz4Dialog(self._ctl.view, self._ctl.theme, plan).ask()
        if request is None:
            return
        if request.remove_source and not dialogs.confirm_warning(remove_confirmation(request)):
            return
        self.tracker = self._new_tracker(host, plan.source.title or plan.source.title_id)
        self.remote.start(host, request)

    def row_for(self, host: str, name: str) -> Lz4Tracker:
        """Obtiene la fila de la conversión (la crea si se retoma una al conectar).

        Args:
            host (str): Dirección de la PS5.
            name (str): Nombre del juego, por si hay que crear la fila.

        Returns:
            Lz4Tracker: Fila activa.
        """
        if self.tracker is None or not self.tracker.is_active:
            self.tracker = self._new_tracker(host, name)
        return self.tracker

    def finished(self, host: str, status: Lz4Status) -> None:
        """Muestra el resultado y, si terminó bien, refresca la carpeta y el espacio.

        Args:
            host (str): Dirección de la PS5.
            status (Lz4Status): Último estado.
        """
        self.row_for(host, job_name(status)).finish(status)
        if status.state is Lz4JobState.DONE and self._ctl.target is not None:
            self._ctl.refresh()

    def rejected(self, check: Lz4Check) -> None:
        """Explica por qué exfat2ampr no inició la conversión.

        Args:
            check (Lz4Check): Comprobación final con errores.
        """
        self.failed(rejection_text(check))

    def failed(self, message: str) -> None:
        """Muestra un error de exfat2ampr (y lo marca en la fila si había una en curso).

        Args:
            message (str): Motivo listo para mostrar.
        """
        self.restore_status()
        if self.tracker is not None and self.tracker.is_active:
            self.tracker.fail(message)
        dialogs.show_error(message)

    def show_status(self, text: str) -> None:
        """Muestra un estado en la barra de conexión (si no hay una escritura en curso).

        Args:
            text (str): Estado a mostrar.
        """
        if self._ctl.view.is_browsing_enabled:
            self._ctl.view.connection.set_state(True, text)

    def restore_status(self) -> None:
        """Vuelve a mostrar la conexión y la carpeta abierta en la barra de conexión."""
        target = self._ctl.target
        if target is not None and self._ctl.view.is_browsing_enabled:
            text = presenters.connection_text(target.host, target.port, self._ctl.path)
            self._ctl.view.connection.set_state(True, text)

    def _new_tracker(self, host: str, name: str) -> Lz4Tracker:
        """Agrega una fila nueva con Cancelar y Reanudar para esa consola.

        Args:
            host (str): Dirección de la PS5.
            name (str): Nombre del juego.

        Returns:
            Lz4Tracker: Fila creada.
        """
        actions = Lz4RowActions(cancel=lambda: self.remote.cancel(host),
                                resume=lambda dest: self.remote.resume(host, dest))
        return Lz4Tracker(self._ctl.view.transfers, name, actions)
