"""Tarjeta de conexión: estado, IP de la PS5, puerto FTP, modo del FTP y botón Conectar."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.config import DEFAULT_FTP_PORT
from ffpfsc_converter.ui.presenters import ConsoleStatus, connection_pill
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import StatusDot

#: Recibe el estado nuevo cada vez que cambia la conexión.
StateListener = Callable[[ConsoleStatus], None]
_TITLES = {"on": "Conectada", "busy": "Conectando…", "off": "Sin conexión"}
_PILL_STYLES = {"wait": "PillWait", "run": "PillRun", "ok": "PillOk", "warn": "PillWarn",
                "bad": "PillBad"}


class ConnectionBar(ttk.Frame):
    """Datos de conexión con la PS5 y estado actual."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, on_connect: Callable[[], None],
                 on_disconnect: Callable[[], None]) -> None:
        """Crea la tarjeta.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            on_connect (Callable[[], None]): Se llama al pulsar "Conectar".
            on_disconnect (Callable[[], None]): Se llama al pulsar "Desconectar".
        """
        m = theme.metrics
        super().__init__(parent, style="Card.TFrame", padding=(m.px(14), m.px(11)))
        self._theme = theme
        self._on_connect, self._on_disconnect = on_connect, on_disconnect
        self._host_var = tk.StringVar()
        self._port_var = tk.StringVar(value=str(DEFAULT_FTP_PORT))
        self._dot = StatusDot(self, theme, "surface")
        self._dot.pack(side="left")
        self._title = ttk.Label(self, style="CardBold.TLabel", width=12)
        self._title.pack(side="left", padx=(m.px(8), m.px(6)))
        self._host = ttk.Entry(self, textvariable=self._host_var, width=15, style="Card.TEntry",
                               font=theme.fonts.mono)
        self._host.pack(side="left")
        self._host.bind("<Return>", lambda _e: self._toggle())
        self._port = ttk.Entry(self, textvariable=self._port_var, width=6, style="Card.TEntry",
                               font=theme.fonts.mono)
        self._port.pack(side="left", padx=(m.px(8), m.px(14)))
        self._button = ttk.Button(self, command=self._toggle, style="Card.Accent.TButton")
        self._button.pack(side="right")
        self._pill = ttk.Label(self)
        self._listeners: list[StateListener] = []
        self._status = ConsoleStatus(False, "", False, "")
        self._host_var.trace_add("write", lambda *_a: self.set_state(
            self._status.connected, self._status.text, self._status.busy))
        self.set_state(False, "")

    def add_listener(self, listener: StateListener) -> None:
        """Registra una función que recibe cada cambio de estado.

        Args:
            listener (StateListener): Recibe el estado nuevo.
        """
        self._listeners.append(listener)

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
        """Actualiza el punto, el título, la píldora y el botón.

        Args:
            connected (bool): ``True`` si hay sesión abierta.
            text (str): Texto de estado (operación en curso o resultado).
            busy (bool): ``True`` mientras se conecta o escribe en la PS5.
        """
        self._status = ConsoleStatus(connected, text, busy, self.host())
        state = "busy" if busy else ("on" if connected else "off")
        self._dot.set_state(state, self._theme.palette)
        self._title.configure(text=_TITLES["on" if connected else state])
        for entry in (self._host, self._port):
            entry.state(["readonly"] if connected or busy else ["!readonly"])
        self._button.configure(text="Desconectar" if connected else "Conectar",
                               style="Card.TButton" if connected else "Card.Accent.TButton")
        self._button.state(["disabled"] if busy else ["!disabled"])
        self._show_pill()
        for listener in self._listeners:
            listener(self._status)

    @property
    def status(self) -> ConsoleStatus:
        """Obtiene el último estado de la conexión.

        Returns:
            ConsoleStatus: Estado actual.
        """
        return self._status

    def _show_pill(self) -> None:
        """Muestra la píldora que corresponde al estado (o la oculta)."""
        pill = connection_pill(self._status)
        if pill is None:
            self._pill.pack_forget()
            return
        self._pill.configure(text=pill.label, style=f"Card.{_PILL_STYLES[pill.kind]}.TLabel")
        self._pill.pack(side="left")

    def _toggle(self) -> None:
        """Conecta o desconecta según el estado actual."""
        (self._on_disconnect if self._status.connected else self._on_connect)()
