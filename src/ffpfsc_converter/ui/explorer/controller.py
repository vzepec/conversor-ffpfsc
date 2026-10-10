"""Controlador de la pestaña PS5: traduce acciones del usuario en llamadas a servicios."""
from __future__ import annotations

import tkinter as tk
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
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui.explorer import presenters
from ffpfsc_converter.ui.explorer.view import ExplorerCallbacks, ExplorerView


class ExplorerController:
    """Coordina la pestaña PS5 con el explorador, el lanzador del FTP y las descargas.

    Attributes:
        view (ExplorerView): Vista de la pestaña.
        launcher (FtpLauncher): Inicia el FTP mediante el helper de ps5upload.
        target (ConsoleTarget | None): Consola conectada, o ``None``.
        path (str): Carpeta remota abierta.
        ftp_restarted (bool): ``True`` si ya se reinició el FTP por credenciales rechazadas.
        browser (RemoteBrowser): Navegación por la PS5.
        downloads (DownloadRunner): Cola de descargas.
    """

    def __init__(self, parent: tk.Misc, emit: EventSink) -> None:
        """Crea la vista y los servicios, y restaura los últimos ajustes.

        Args:
            parent (tk.Misc): Pestaña donde se construye la vista.
            emit (EventSink): Cola de eventos de la ventana principal.
        """
        self.view = ExplorerView(parent, ExplorerCallbacks(
            on_connect=self.connect, on_disconnect=self.disconnect,
            on_open_entry=self.open_entry, on_go_up=self.go_up, on_go_to=self.go_to,
            on_refresh=self.refresh, on_download=self.download,
            on_change_destination=self.change_destination,
            on_cancel_downloads=self.cancel_downloads,
            on_open_destination=self.open_destination,
        ))
        self.launcher = FtpLauncher(emit, TrustStore(settings_path().parent))
        self.browser = RemoteBrowser(emit)
        self.downloads = DownloadRunner(emit)
        self.target: ConsoleTarget | None = None
        self.path = "/"
        self.ftp_restarted = False
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
        save_settings({"ps5_host": host, "ps5_ftp_port": port})
        self.view.connection.set_state(False, f"Conectando con {host}…", busy=True)
        self.launcher.connect(host, port, restart=restart)

    def disconnect(self) -> None:
        """Cierra la sesión del explorador (las descargas en curso continúan)."""
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
        """Vuelve a listar la carpeta actual."""
        self.browser.open(self.path)

    def download(self) -> None:
        """Encola la descarga de los elementos seleccionados."""
        entries = self.view.remote.selected_entries()
        if not entries:
            dialogs.show_info("Selecciona uno o más archivos o carpetas de la PS5.")
            return
        if self.target is None:
            dialogs.show_error("No hay conexión con la PS5.")
            return
        if self.downloads.is_running:
            dialogs.show_info("Espera a que terminen las descargas en curso.")
            return
        if self.download_dir is None and not self._choose_destination():
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
        self._choose_destination()

    def cancel_downloads(self) -> None:
        """Cancela las descargas (los archivos a medias se pueden reanudar)."""
        self.downloads.cancel()

    def open_destination(self) -> None:
        """Abre la carpeta de descargas en el gestor de archivos."""
        if self.download_dir is not None:
            open_in_file_manager(self.download_dir)

    def _choose_destination(self) -> bool:
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
