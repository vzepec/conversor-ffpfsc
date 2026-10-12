"""Ventana principal: compone la barra lateral y las vistas, y reparte los eventos.

Los servicios publican eventos desde hilos de fondo en ``self._events``;
:meth:`MainWindow._poll_events` los consume en el hilo de la interfaz y los
entrega a quien corresponda: la vista PS5, la vista Convertir o la barra lateral.
"""
from __future__ import annotations

import queue
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType

from ffpfsc_converter.config import AUTO_CONNECT_DELAY_MS
from ffpfsc_converter.domain.events import Event
from ffpfsc_converter.domain.remote_events import RemoteEvent
from ffpfsc_converter.domain.update import UpdateAvailable
from ffpfsc_converter.infrastructure.app_log import log_dir, setup_file_log
from ffpfsc_converter.services.update_check import start_update_check
from ffpfsc_converter.ui import dialogs, presenters, theme
from ffpfsc_converter.ui.activity import ActivityWatch
from ffpfsc_converter.ui.convert_controller import ConvertController, ConvertLinks
from ffpfsc_converter.ui.event_journal import journal_line
from ffpfsc_converter.ui.explorer.controller import ExplorerController
from ffpfsc_converter.ui.explorer.updater import ExplorerUpdater
from ffpfsc_converter.ui.notifications import Notifier
from ffpfsc_converter.ui.shell import AppShell
from ffpfsc_converter.ui.window import create_window, remember_window


class MainWindow:
    """Ventana principal: barra lateral, vista Convertir y vista PS5."""

    def __init__(self, initial_paths: Iterable[Path] = ()) -> None:
        """Crea la ventana y encola las rutas iniciales.

        Args:
            initial_paths (Iterable[Path]): Rutas recibidas por línea de comandos.
        """
        self._log = setup_file_log(log_dir())
        self._window = create_window()
        self.root, self.theme = self._window.root, self._window.theme
        self._events: queue.Queue[Event | RemoteEvent] = queue.Queue()
        self._shell = AppShell(self.root, self.theme, presenters.version_text())
        self._shell.pack(fill="both", expand=True)
        convert_tab = self._shell.add_view("convert", "Convertir", "convert")
        ps5_tab = self._shell.add_view("ps5", "PS5", "console")
        self._explorer = ExplorerController(ps5_tab, self.theme, self._events.put)
        self._explorer.view.pack(fill="both", expand=True)
        self._explorer.view.add_status_listener(
            lambda status: self._shell.show_connection(presenters.connection_card(status)))
        self._explorer.view.transfers.add_listener(
            lambda active: self._shell.set_badge("ps5", str(active) if active else ""))
        self._explorer_updater = ExplorerUpdater(self._explorer)
        self._convert = ConvertController(convert_tab, self.theme, self._events.put, ConvertLinks(
            self._explorer,
            lambda count: self._shell.set_badge("convert", str(count) if count else ""),
            lambda: self._shell.show("ps5")))
        self._shell.show(self._window.saved.view)
        self.root.report_callback_exception = self._on_unexpected
        threading.excepthook = lambda args: self._log.error(
            "Error inesperado en un hilo", exc_info=(args.exc_type, args.exc_value,
                                                     args.exc_traceback))
        self._notifier = Notifier(self.root)
        self._activity = ActivityWatch(self.root, self._is_busy)
        self.root.after(theme.EVENT_POLL_MS, self._poll_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._convert.add_paths(initial_paths)
        start_update_check(self._events.put)
        self.root.after(AUTO_CONNECT_DELAY_MS, self._explorer.auto_connect)

    def run(self) -> None:
        """Inicia el bucle principal de Tkinter hasta que se cierra la ventana."""
        self.root.mainloop()

    def _on_close(self) -> None:
        """Cierra la ventana, cancelando antes las tareas en curso si el usuario acepta."""
        if self._convert.runner.is_running and not dialogs.confirm_quit_while_running():
            return
        if self._explorer.downloads.is_running and not dialogs.confirm_quit_while_downloading():
            return
        self._explorer.downloads.cancel()
        self._convert.runner.cancel()
        self._activity.stop()
        remember_window(self.root, self._shell.current)
        self.root.destroy()

    def _poll_events(self) -> None:
        """Entrega los eventos pendientes sin pasar del presupuesto de tiempo y se reprograma.

        Si llegan más eventos de los que caben en el presupuesto, se cede el control
        a Tk (para que la ventana siga respondiendo) y se continúa enseguida.
        """
        deadline = time.monotonic() + theme.EVENT_BUDGET_MS / 1000
        pending = True
        try:
            while time.monotonic() < deadline:
                self._dispatch(self._events.get_nowait())
        except queue.Empty:
            pending = False
        self.root.after(1 if pending else theme.EVENT_POLL_MS, self._poll_events)

    def _dispatch(self, event: Event | RemoteEvent) -> None:
        """Entrega un evento a la vista que lo maneja.

        Args:
            event (Event | RemoteEvent): Evento publicado por un servicio.
        """
        self._notifier.handle(event)
        entry = journal_line(event)
        if entry is not None:
            self._log.log(entry.level, entry.text)
        if self._explorer_updater.handles(event):
            self._explorer_updater.handle(event)
        elif isinstance(event, UpdateAvailable):
            self._shell.show_update(event.release)
        else:
            self._convert.handle(event)

    def _is_busy(self) -> bool:
        """Indica si hay una tarea larga en curso (conversión o transferencia con la PS5).

        Returns:
            bool: ``True`` mientras no conviene que el equipo se suspenda.
        """
        return (self._convert.runner.is_running or self._explorer.downloads.is_running
                or self._explorer.modify.busy)

    def _on_unexpected(self, kind: type[BaseException], error: BaseException,
                       trace: TracebackType | None) -> None:
        """Guarda en el registro un error no previsto de la interfaz y lo informa.

        Args:
            kind (type[BaseException]): Tipo de la excepción.
            error (BaseException): Excepción.
            trace (TracebackType | None): Traza.
        """
        self._log.error("Error inesperado en la interfaz", exc_info=(kind, error, trace))
        dialogs.show_error(f"Ocurrió un error inesperado ({error}).\n\nEl detalle quedó en "
                           f"el registro:\n{log_dir()}")
