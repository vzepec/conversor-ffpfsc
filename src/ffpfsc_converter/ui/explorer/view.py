"""Vista de la pestaña PS5: compone la barra de conexión, el explorador y las descargas."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

from ffpfsc_converter.config import PS5_FAVORITE_PATHS
from ffpfsc_converter.domain.remote import RemoteEntry
from ffpfsc_converter.ui import theme
from ffpfsc_converter.ui.explorer.connection_bar import ConnectionBar
from ffpfsc_converter.ui.explorer.remote_list import RemoteList
from ffpfsc_converter.ui.explorer.transfer_panel import TransferPanel

_HINT = ("Doble clic para abrir una carpeta. «Comprimir y reemplazar» descarga el juego, lo "
         "comprime y sustituye el original en la PS5 por el .ffpfsc verificado.")


@dataclass(frozen=True)
class ExplorerCallbacks:
    """Acciones del usuario en la pestaña PS5.

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
    """Widgets de la pestaña PS5.

    Attributes:
        connection (ConnectionBar): IP, puerto y estado de la conexión.
        remote (RemoteList): Contenido de la carpeta remota abierta.
        transfers (TransferPanel): Cola de descargas.
    """

    def __init__(self, parent: tk.Misc, callbacks: ExplorerCallbacks) -> None:
        """Construye la pestaña.

        Args:
            parent (tk.Misc): Contenedor (la pestaña del ``Notebook``).
            callbacks (ExplorerCallbacks): Acciones a notificar al controlador.
        """
        super().__init__(parent)
        self.connection = ConnectionBar(self, callbacks.on_connect, callbacks.on_disconnect)
        self.connection.pack(fill="x", **theme.PADDING)
        self._build_path_bar(callbacks)
        self.remote = RemoteList(self, callbacks.on_open_entry)
        self.remote.pack(fill="both", expand=True, **theme.PADDING)
        actions = ttk.Frame(self)
        actions.pack(fill="x", **theme.PADDING)
        self._actions = [
            ttk.Button(actions, text="⬇ Descargar", command=callbacks.on_download),
            ttk.Button(actions, text="⬆ Subir archivo…", command=callbacks.on_upload),
            ttk.Button(actions, text="♻ Comprimir y reemplazar…", command=callbacks.on_convert),
            ttk.Button(actions, text="🗑 Eliminar", command=callbacks.on_delete),
        ]
        for button in self._actions:
            button.pack(side="left", padx=(0, 6))
        ttk.Label(self, text=_HINT, foreground=theme.HINT_FG).pack(anchor="w", padx=10)
        self.transfers = TransferPanel(self, callbacks.on_change_destination,
                                       callbacks.on_cancel_downloads,
                                       callbacks.on_open_destination,
                                       callbacks.on_retry_failed)
        self.transfers.pack(fill="both", **theme.PADDING)
        self.set_browsing_enabled(False)

    def _build_path_bar(self, callbacks: ExplorerCallbacks) -> None:
        """Crea la barra de ruta con "Subir", accesos rápidos y "Actualizar".

        Args:
            callbacks (ExplorerCallbacks): Acciones a notificar al controlador.
        """
        bar = ttk.Frame(self)
        bar.pack(fill="x", **theme.PADDING)
        self._up = ttk.Button(bar, text="⬆ Subir", command=callbacks.on_go_up)
        self._up.pack(side="left")
        self._path_var = tk.StringVar(value="/")
        self._path = ttk.Combobox(bar, textvariable=self._path_var,
                                  values=list(PS5_FAVORITE_PATHS))
        self._path.pack(side="left", fill="x", expand=True, padx=6)
        self._path.bind("<Return>", lambda _e: callbacks.on_go_to(self._path_var.get()))
        self._path.bind("<<ComboboxSelected>>",
                        lambda _e: callbacks.on_go_to(self._path_var.get()))
        self._refresh = ttk.Button(bar, text="↻ Actualizar", command=callbacks.on_refresh)
        self._refresh.pack(side="left")

    def set_path(self, path: str) -> None:
        """Muestra la carpeta remota abierta.

        Args:
            path (str): Ruta absoluta.
        """
        self._path_var.set(path)

    def set_browsing_enabled(self, enabled: bool) -> None:
        """Habilita la navegación y la descarga solo con conexión.

        Args:
            enabled (bool): ``True`` si hay sesión con la PS5.
        """
        state = "normal" if enabled else "disabled"
        for widget in (self._up, self._path, self._refresh, *self._actions):
            widget.configure(state=state)
