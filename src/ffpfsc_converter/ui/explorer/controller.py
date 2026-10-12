"""Controlador de la vista PS5: traduce acciones del usuario en llamadas a servicios."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path

from ffpfsc_converter.config import DEFAULT_FTP_PORT
from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.remote import ConsoleTarget, DownloadJob, RemoteEntry
from ffpfsc_converter.infrastructure.ava1.trust import TrustStore
from ffpfsc_converter.infrastructure.ftp.listing import join_remote
from ffpfsc_converter.infrastructure.settings_store import (
    load_settings,
    save_settings,
    settings_path,
)
from ffpfsc_converter.infrastructure.system import open_in_file_manager
from ffpfsc_converter.services.downloads import DownloadRunner
from ffpfsc_converter.services.ftp_launcher import FtpLauncher
from ffpfsc_converter.services.remote_browser import RemoteBrowser
from ffpfsc_converter.services.remote_storage import StorageMonitor
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.explorer import presenters
from ffpfsc_converter.ui.explorer.modify_actions import ModifyActions
from ffpfsc_converter.ui.explorer.retry_actions import RetryActions
from ffpfsc_converter.ui.explorer.view import ExplorerCallbacks, ExplorerView
from ffpfsc_converter.ui.theme import ThemeManager


class ExplorerController:
    """Coordina la vista PS5 con el explorador, el lanzador del FTP y las descargas.

    Attributes:
        theme (ThemeManager): Tema (para los diálogos).
        view (ExplorerView): Vista de la vista.
        launcher (FtpLauncher): Inicia el FTP mediante el helper de ps5upload.
        target (ConsoleTarget | None): Consola conectada, o ``None``.
        path (str): Carpeta remota abierta.
        entries (tuple[RemoteEntry, ...]): Contenido de la carpeta abierta.
        modify (ModifyActions): Eliminar, subir y comprimir y reemplazar.
        retry (RetryActions): Reintento manual de transferencias fallidas.
        upload_listeners (dict[str, Callable[[object], None]]): Fila de subida → función
            que también recibe sus eventos (la vista Convertir sigue así sus subidas).
        pending_on_connect (list[Callable[[], None]]): Acciones a ejecutar al conectar.
        ftp_restarted (bool): ``True`` si ya se reinició el FTP por credenciales rechazadas.
        quiet (bool): ``True`` durante una conexión automática (sin diálogos de error).
        user_disconnected (bool): ``True`` si el usuario pulsó «Desconectar» (no se reconecta).
        reconnects (int): Intentos de reconexión automática hechos tras un corte.
        needs_restart (bool): ``True`` si al reconectar hay que reiniciar el FTP (por
            ejemplo, si no volvió a solo lectura tras una subida).
        browser (RemoteBrowser): Navegación por la PS5.
        downloads (DownloadRunner): Cola de descargas.
        storage (StorageMonitor): Espacio libre de las unidades de la PS5.
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager, emit: EventSink) -> None:
        """Crea la vista y los servicios, y restaura los últimos ajustes.

        Args:
            parent (tk.Misc): Contenedor donde se construye la vista.
            theme (ThemeManager): Tema.
            emit (EventSink): Cola de eventos de la ventana principal.
        """
        self.theme = theme
        self.view = ExplorerView(parent, theme, ExplorerCallbacks(
            on_connect=self.connect, on_disconnect=self.disconnect,
            on_open_entry=self.open_entry, on_go_up=self.go_up, on_go_to=self.go_to,
            on_refresh=self.refresh, on_download=self.download,
            on_change_destination=self.change_destination,
            on_cancel_downloads=self.cancel_downloads,
            on_open_destination=self.open_destination,
            on_retry_failed=lambda: self.retry.retry_failed(),
            on_clear_transfers=lambda: self.retry.forget(self.view.transfers.remove_finished()),
            on_upload=lambda: self.modify.upload_files(),
            on_upload_folder=lambda: self.modify.upload_folder(),
            on_delete=lambda: self.modify.delete_selected(),
            on_convert=lambda: self.modify.convert_selected(),
        ))
        self._trust = TrustStore(settings_path().parent)
        self.launcher = FtpLauncher(emit, self._trust)
        self.browser = RemoteBrowser(emit)
        self.downloads = DownloadRunner(emit)
        self.storage = StorageMonitor(emit, self.launcher.access)
        self.modify = ModifyActions(self, emit, self.launcher.access)
        self.retry = RetryActions(self)
        self.target: ConsoleTarget | None = None
        self.path = "/"
        self.entries: tuple[RemoteEntry, ...] = ()
        self.upload_listeners: dict[str, Callable[[object], None]] = {}
        self.pending_on_connect: list[Callable[[], None]] = []
        self.ftp_restarted = False
        self.quiet, self.user_disconnected, self.reconnects = False, False, 0
        self.needs_restart = False
        settings = load_settings()
        self.download_dir = Path(settings["download_dir"]) if settings.get("download_dir") else None
        self.view.connection.set_values(str(settings.get("ps5_host", "")),
                                        int(settings.get("ps5_ftp_port", DEFAULT_FTP_PORT)))
        self.view.transfers.set_destination(self.download_dir)

    def connect(self, restart: bool = False) -> None:
        """Inicia (si hace falta) el FTP de la PS5 y se conecta.

        Args:
            restart (bool): ``True`` para reiniciar el FTP con credenciales nuevas.
        """
        host, port = self.view.connection.host(), self.view.connection.port()
        if not host or port is None:
            dialogs.show_error("Escribe la IP de la PS5 y un puerto FTP válido.")
            return
        self.quiet, self.user_disconnected, self.reconnects = False, False, 0
        save_settings({"ps5_host": host, "ps5_ftp_port": port})
        self.view.connection.set_state(False, f"Conectando con {host}…", busy=True)
        self.launcher.connect(host, port, restart=restart or self.needs_restart)

    def auto_connect(self) -> None:
        """Se conecta sin molestar si la PS5 ya está vinculada (al abrir o tras un corte).

        No muestra errores ni pide el código de emparejamiento; si la consola no
        responde, se rinde enseguida.
        """
        host, port = self.view.connection.host(), self.view.connection.port()
        if (not host or port is None or self.target is not None
                or self._trust.known_key(host) is None):
            return
        self.quiet = True
        self.view.connection.set_state(False, f"Conectando con {host}…", busy=True)
        self.launcher.connect(host, port, restart=self.needs_restart, quick=True)

    def when_connected(self, action: Callable[[], None]) -> None:
        """Ejecuta una acción ahora si hay conexión o, si no, apenas se conecte.

        Args:
            action (Callable[[], None]): Acción a ejecutar (por ejemplo, una subida).
        """
        if self.target is not None:
            action()
        else:
            self.pending_on_connect.append(action)

    def disconnect(self) -> None:
        """Cierra la sesión del explorador (las descargas en curso continúan)."""
        self.user_disconnected = True
        self.browser.disconnect()

    def open_entry(self, entry: RemoteEntry) -> None:
        """Abre una carpeta con doble clic (los archivos se descargan con el botón).

        Args:
            entry (RemoteEntry): Elemento elegido.
        """
        if entry.is_dir:
            self.browser.open(entry.path)

    def go_up(self) -> None:
        """Abre la carpeta superior."""
        self.browser.open(presenters.parent_path(self.path))

    def go_to(self, path: str) -> None:
        """Abre una ruta escrita o elegida en los accesos rápidos.

        Args:
            path (str): Ruta remota (se normaliza como absoluta).
        """
        self.browser.open(join_remote("/", path.strip() or "/"))

    def refresh(self) -> None:
        """Vuelve a listar la carpeta actual y el espacio de las unidades."""
        self.browser.open(self.path)
        self.refresh_storage()

    def refresh_storage(self) -> None:
        """Vuelve a consultar el espacio libre de las unidades, si hay conexión."""
        if self.target is not None:
            self.storage.refresh(self.target.host)

    def download(self) -> None:
        """Encola la descarga de los elementos seleccionados."""
        entries = self.view.remote.selected_entries()
        if not entries:
            dialogs.show_info("Selecciona uno o más archivos o carpetas de la PS5.")
            return
        if self.target is None:
            dialogs.show_error("No hay conexión con la PS5.")
            return
        if self.downloads.is_running or self.modify.busy:
            dialogs.show_info("Espera a que termine la operación en curso.")
            return
        if self.download_dir is None and not self.choose_destination():
            return
        assert self.download_dir is not None
        jobs = [DownloadJob(entry, self.download_dir) for entry in entries]
        if not all(not j.local_path.exists() or dialogs.confirm_resume_download(j.local_path)
                   for j in jobs):
            return
        for job in jobs:
            self.view.transfers.add_job(job)
        self.view.transfers.set_running(True)
        self.downloads.start(jobs, self.target)

    def change_destination(self) -> None:
        """Pide una carpeta de descargas nueva."""
        self.choose_destination()

    def cancel_downloads(self) -> None:
        """Cancela las descargas (los archivos a medias se pueden reanudar)."""
        self.downloads.cancel()

    def open_destination(self) -> None:
        """Abre la carpeta de descargas en el gestor de archivos."""
        if self.download_dir is not None:
            open_in_file_manager(self.download_dir)

    def choose_destination(self) -> bool:
        """Pide la carpeta de descargas y la guarda en los ajustes.

        Returns:
            bool: ``True`` si el usuario eligió una carpeta.
        """
        folder = dialogs.ask_download_dir()
        if folder is None:
            return False
        self.download_dir = folder
        self.view.transfers.set_destination(folder)
        save_settings({"download_dir": str(folder)})
        return True
