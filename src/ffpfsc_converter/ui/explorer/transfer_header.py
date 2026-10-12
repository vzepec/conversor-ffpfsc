"""Encabezado del panel de transferencias: título, carpeta de descargas y botones."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.ui.explorer.transfer_presenters import destination_text
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import icon_button


@dataclass(frozen=True)
class TransferActions:
    """Acciones del encabezado del panel.

    Attributes:
        change_destination (Callable[[], None]): Enlace "Cambiar".
        open_destination (Callable[[], None]): Enlace "Abrir".
        retry_failed (Callable[[], None]): Botón "Reintentar fallidas".
        cancel (Callable[[], None]): Botón "Cancelar".
        clear_finished (Callable[[], None]): Botón "Limpiar" (quita lo que ya terminó).
    """

    change_destination: Callable[[], None]
    open_destination: Callable[[], None]
    retry_failed: Callable[[], None]
    cancel: Callable[[], None]
    clear_finished: Callable[[], None]


class TransferHeader(ttk.Frame):
    """Título con el contador, carpeta de descargas y botones del panel."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, actions: TransferActions) -> None:
        """Crea el encabezado con los botones deshabilitados.

        Args:
            parent (tk.Misc): Panel de transferencias.
            theme (ThemeManager): Tema.
            actions (TransferActions): Acciones de los botones.
        """
        m = theme.metrics
        super().__init__(parent, style="Surface.TFrame", padding=(m.px(10), m.px(6)))
        self._title = ttk.Label(self, style="CardBold.TLabel")
        self._title.pack(side="left")
        self._cancel = icon_button(self, theme, "Cancelar", "stop", actions.cancel,
                                   style="Card.SmallDanger.TButton", role="bad")
        self._cancel.pack(side="right")
        self._retry = icon_button(self, theme, "Reintentar fallidas", "retry",
                                  actions.retry_failed, style="Card.Small.TButton")
        self._retry.pack(side="right", padx=(0, m.px(8)))
        self._clear = icon_button(self, theme, "Limpiar", "x", actions.clear_finished,
                                  style="Card.Small.TButton")
        self._clear.pack(side="right", padx=(0, m.px(8)))
        for text, command in (("Abrir", actions.open_destination),
                              ("Cambiar", actions.change_destination)):
            ttk.Button(self, text=text, style="Card.Link.TButton", cursor="hand2",
                       command=command).pack(side="right", padx=(m.px(8), m.px(8)))
        self._destination = ttk.Label(self, style="CardSmall.TLabel")
        self._destination.pack(side="right", padx=(m.px(12), 0))
        for button in (self._cancel, self._retry, self._clear):
            button.state(["disabled"])

    def show_counts(self, total: int, finished: int) -> None:
        """Muestra cuántas filas hay y habilita «Limpiar» si alguna ya terminó.

        Args:
            total (int): Filas en el panel.
            finished (int): Filas que ya no están en cola ni en curso.
        """
        self._title.configure(text=f"Transferencias · {total}" if total else "Transferencias")
        self._clear.state(["!disabled"] if finished else ["disabled"])

    def set_destination(self, folder: Path | None) -> None:
        """Muestra la carpeta de descargas.

        Args:
            folder (Path | None): Carpeta elegida, o ``None`` si aún no hay.
        """
        self._destination.configure(text=destination_text(folder, Path.home()))

    def set_running(self, running: bool) -> None:
        """Habilita "Cancelar" solo mientras hay descargas.

        Args:
            running (bool): ``True`` si hay descargas en curso.
        """
        self._cancel.state(["!disabled"] if running else ["disabled"])

    def set_retry_enabled(self, enabled: bool) -> None:
        """Habilita "Reintentar fallidas" solo si hay transferencias fallidas.

        Args:
            enabled (bool): ``True`` si hay algo que reintentar.
        """
        self._retry.state(["!disabled"] if enabled else ["disabled"])
