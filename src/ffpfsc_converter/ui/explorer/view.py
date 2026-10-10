"""Vista PS5: conexión, unidades, ruta, archivos, acciones y transferencias."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from tkinter import ttk

from ffpfsc_converter.config import PS5_FAVORITE_PATHS
from ffpfsc_converter.domain.remote import RemoteEntry, StorageVolume
from ffpfsc_converter.ui.explorer.action_bar import ActionBar
from ffpfsc_converter.ui.explorer.connection_bar import ConnectionBar
from ffpfsc_converter.ui.explorer.drives import DriveStrip
from ffpfsc_converter.ui.explorer.file_list import FileList
from ffpfsc_converter.ui.explorer.path_bar import PathBar
from ffpfsc_converter.ui.explorer.transfer_panel import TransferActions, TransferPanel
from ffpfsc_converter.ui.explorer.view_presenters import (
    action_states,
    drive_cards,
    internal_free_text,
    selection_text,
)
from ffpfsc_converter.ui.presenters import ConsoleStatus
from ffpfsc_converter.ui.theme import ThemeManager


@dataclass(frozen=True)
class ExplorerCallbacks:
    """Acciones del usuario en la vista PS5.

    Attributes:
        on_connect (Callable[[], None]): Botón "Conectar".
        on_disconnect (Callable[[], None]): Botón "Desconectar".
        on_open_entry (Callable[[RemoteEntry], None]): Doble clic en un elemento.
        on_go_up (Callable[[], None]): Botón "Subir".
        on_go_to (Callable[[str], None]): Ruta escrita o acceso rápido elegido.
        on_refresh (Callable[[], None]): Botón "Actualizar".
        on_download (Callable[[], None]): Botón "Descargar".
        on_change_destination (Callable[[], None]): Cambiar carpeta de descargas.
        on_cancel_downloads (Callable[[], None]): Cancelar descargas.
        on_open_destination (Callable[[], None]): Abrir carpeta de descargas.
        on_retry_failed (Callable[[], None]): Reintentar transferencias fallidas.
        on_upload (Callable[[], None]): Botón "Subir archivo".
        on_delete (Callable[[], None]): Botón "Eliminar".
        on_convert (Callable[[], None]): Botón "Comprimir y reemplazar".
    """

    on_connect: Callable[[], None]
    on_disconnect: Callable[[], None]
    on_open_entry: Callable[[RemoteEntry], None]
    on_go_up: Callable[[], None]
    on_go_to: Callable[[str], None]
    on_refresh: Callable[[], None]
    on_download: Callable[[], None]
    on_change_destination: Callable[[], None]
    on_cancel_downloads: Callable[[], None]
    on_open_destination: Callable[[], None]
    on_retry_failed: Callable[[], None]
    on_upload: Callable[[], None]
    on_delete: Callable[[], None]
    on_convert: Callable[[], None]


class ExplorerView(ttk.Frame):
    """Widgets de la vista PS5.

    Attributes:
        connection (ConnectionBar): IP, puerto y estado de la conexión.
        remote (FileList): Contenido de la carpeta remota abierta.
        transfers (TransferPanel): Descargas y subidas.
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager, callbacks: ExplorerCallbacks) -> None:
        """Construye la vista.

        Args:
            parent (tk.Misc): Contenedor de la vista.
            theme (ThemeManager): Tema.
            callbacks (ExplorerCallbacks): Acciones a notificar al controlador.
        """
        m = theme.metrics
        super().__init__(parent, style="TFrame", padding=(m.px(26), m.px(22)))
        self._connected = False
        self._volumes: tuple[StorageVolume, ...] = ()
        self._listeners: list[Callable[[ConsoleStatus], None]] = []
        head = ttk.Frame(self, style="TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="PS5", style="Title.TLabel").pack(anchor="w")
        ttk.Label(head, text="Explora, descarga, sube y reemplaza juegos en la consola",
                  style="Muted.TLabel").pack(anchor="w")
        self.connection = ConnectionBar(self, theme, callbacks.on_connect, callbacks.on_disconnect)
        self.connection.pack(fill="x", pady=(m.px(16), 0))
        self.connection.add_listener(lambda _s: self._notify())
        self._drives = DriveStrip(self, theme)
        self._drives.pack(fill="x", pady=(m.px(12), 0))
        self.transfers = TransferPanel(self, theme, TransferActions(
            callbacks.on_change_destination, callbacks.on_open_destination,
            callbacks.on_retry_failed, callbacks.on_cancel_downloads))
        self.transfers.pack(side="bottom", fill="x", pady=(m.px(12), 0))
        self._actions = ActionBar(self, theme, {
            "download": callbacks.on_download, "convert": callbacks.on_convert,
            "upload": callbacks.on_upload, "delete": callbacks.on_delete})
        self._actions.pack(side="bottom", fill="x", pady=(m.px(10), 0))
        self._path = PathBar(self, theme, PS5_FAVORITE_PATHS,
                             (callbacks.on_go_up, callbacks.on_go_to, callbacks.on_refresh))
        self._path.pack(fill="x", pady=(m.px(12), m.px(10)))
        self.remote = FileList(self, theme, callbacks.on_open_entry, self._on_selection)
        self.remote.pack(fill="both", expand=True)
        self.set_storage((), "")
        self.set_browsing_enabled(False)

    def add_status_listener(self, listener: Callable[[ConsoleStatus], None]) -> None:
        """Registra una función que recibe el estado de la conexión y el espacio libre.

        Args:
            listener (Callable[[ConsoleStatus], None]): Recibe el estado nuevo.
        """
        self._listeners.append(listener)

    def set_path(self, path: str) -> None:
        """Muestra la carpeta remota abierta.

        Args:
            path (str): Ruta absoluta.
        """
        self._path.set_path(path)

    def set_storage(self, volumes: Iterable[StorageVolume], error: str) -> None:
        """Muestra el espacio de las unidades de la PS5.

        Args:
            volumes (Iterable[StorageVolume]): Unidades montadas.
            error (str): Motivo si no se pudo consultar (las tarjetas quedan sin datos).
        """
        self._volumes = () if error else tuple(volumes)
        self._drives.show(drive_cards(self._volumes, self._connected and not error))
        self._notify()

    def set_browsing_enabled(self, enabled: bool) -> None:
        """Habilita la navegación y las acciones solo con conexión.

        Args:
            enabled (bool): ``True`` si hay sesión con la PS5.
        """
        self._connected = enabled
        self._path.set_enabled(enabled)
        if not enabled:
            self._drives.show(drive_cards((), False))
        self._on_selection()

    def _on_selection(self) -> None:
        """Actualiza la barra de acciones según la selección."""
        selected = self.remote.selected_entries()
        self._actions.show(selection_text(len(selected)),
                           action_states(self._connected, selected))

    def _notify(self) -> None:
        """Avisa el estado de la conexión junto con el espacio libre del disco interno."""
        status = replace(self.connection.status, free_text=internal_free_text(self._volumes))
        for listener in self._listeners:
            listener(status)
