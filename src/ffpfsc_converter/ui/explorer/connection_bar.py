"""Barra de conexión: IP de la PS5, puerto FTP, botón Conectar y estado."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.config import DEFAULT_FTP_PORT


class ConnectionBar(ttk.Frame):
    """Datos de conexión con la PS5 y estado actual."""

    def __init__(
        self,
        parent: tk.Misc,
        on_connect: Callable[[], None],
        on_disconnect: Callable[[], None],
    ) -> None:
        """Crea los controles.

        Args:
            parent (tk.Misc): Contenedor.
            on_connect (Callable[[], None]): Se llama al pulsar "Conectar".
            on_disconnect (Callable[[], None]): Se llama al pulsar "Desconectar".
        """
        super().__init__(parent)
        self._on_connect, self._on_disconnect = on_connect, on_disconnect
        self._host_var = tk.StringVar()
        self._port_var = tk.StringVar(value=str(DEFAULT_FTP_PORT))
        ttk.Label(self, text="IP de la PS5:").pack(side="left")
        host = ttk.Entry(self, textvariable=self._host_var, width=16)
        host.pack(side="left", padx=(4, 12))
        host.bind("<Return>", lambda _e: self._toggle())
        ttk.Label(self, text="Puerto FTP:").pack(side="left")
        ttk.Entry(self, textvariable=self._port_var, width=6).pack(side="left", padx=(4, 12))
        self._button = ttk.Button(self, text="Conectar", command=self._toggle)
        self._button.pack(side="left")
        self._status = ttk.Label(self, text="Sin conexión.")
        self._status.pack(side="left", padx=12)
        self._connected = False

    def host(self) -> str:
        """Obtiene la IP escrita.

        Returns:
            str: Dirección sin espacios.
        """
        return self._host_var.get().strip()

    def port(self) -> int | None:
        """Obtiene el puerto FTP escrito.

        Returns:
            int | None: Puerto válido (1-65535), o ``None`` si no lo es.
        """
        try:
            value = int(self._port_var.get())
        except ValueError:
            return None
        return value if 0 < value < 65536 else None

    def set_values(self, host: str, port: int) -> None:
        """Rellena la IP y el puerto (por ejemplo, con los últimos usados).

        Args:
            host (str): Dirección de la PS5.
            port (int): Puerto FTP.
        """
        self._host_var.set(host)
        self._port_var.set(str(port))

    def set_state(self, connected: bool, text: str, busy: bool = False) -> None:
        """Actualiza el botón y el texto de estado.

        Args:
            connected (bool): ``True`` si hay sesión abierta.
            text (str): Texto de estado.
            busy (bool): ``True`` mientras se conecta (deshabilita el botón).
        """
        self._connected = connected
        self._button.configure(text="Desconectar" if connected else "Conectar",
                               state="disabled" if busy else "normal")
        self._status.configure(text=text)

    def _toggle(self) -> None:
        """Conecta o desconecta según el estado actual."""
        (self._on_disconnect if self._connected else self._on_connect)()
