"""Panel de transferencias: descargas y subidas con su avance, velocidad y tiempo restante."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.domain.remote import DownloadJob, DownloadResult
from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.ui.explorer import presenters
from ffpfsc_converter.ui.explorer.transfer_presenters import (
    destination_text,
    download_result_status,
    transfer_progress,
)
from ffpfsc_converter.ui.explorer.transfer_row import TransferRow
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import icon_button
from ffpfsc_converter.ui.widgets.scroll_frame import ScrollFrame

_VISIBLE_ROWS = 3


@dataclass(frozen=True)
class TransferActions:
    """Acciones del encabezado del panel.

    Attributes:
        change_destination (Callable[[], None]): Enlace "Cambiar".
        open_destination (Callable[[], None]): Enlace "Abrir".
        retry_failed (Callable[[], None]): Botón "Reintentar fallidas".
        cancel (Callable[[], None]): Botón "Cancelar".
    """

    change_destination: Callable[[], None]
    open_destination: Callable[[], None]
    retry_failed: Callable[[], None]
    cancel: Callable[[], None]


class TransferPanel(ttk.Frame):
    """Cola de transferencias con la PS5."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, actions: TransferActions) -> None:
        """Crea el panel vacío.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            actions (TransferActions): Acciones del encabezado.
        """
        m = theme.metrics
        super().__init__(parent, style="Card.TFrame", padding=m.px(4))
        self._theme = theme
        self._rows: dict[str, TransferRow] = {}
        self._listeners: list[Callable[[int], None]] = []
        self._build_header(actions)
        self._list = ScrollFrame(self, theme)
        self._list.configure(height=m.px(_VISIBLE_ROWS * 52))
        self._list.pack_propagate(False)

    def _build_header(self, actions: TransferActions) -> None:
        """Crea el título, la carpeta de descargas y los botones.

        Args:
            actions (TransferActions): Acciones del encabezado.
        """
        m, theme = self._theme.metrics, self._theme
        head = ttk.Frame(self, style="Surface.TFrame", padding=(m.px(10), m.px(6)))
        head.pack(fill="x")
        self._title = ttk.Label(head, style="CardBold.TLabel")
        self._title.pack(side="left")
        self._cancel = icon_button(head, theme, "Cancelar", "stop", actions.cancel,
                                   style="Card.SmallDanger.TButton", role="bad")
        self._cancel.pack(side="right")
        self._retry = icon_button(head, theme, "Reintentar fallidas", "retry",
                                  actions.retry_failed, style="Card.Small.TButton")
        self._retry.pack(side="right", padx=(0, m.px(8)))
        for text, command in (("Abrir", actions.open_destination),
                              ("Cambiar", actions.change_destination)):
            ttk.Button(head, text=text, style="Card.Link.TButton", cursor="hand2",
                       command=command).pack(side="right", padx=(m.px(8), m.px(8)))
        self._destination = ttk.Label(head, style="CardSmall.TLabel")
        self._destination.pack(side="right", padx=(m.px(12), 0))
        self._separator = ttk.Separator(self)
        self.set_running(False)
        self.set_retry_enabled(False)
        self._update_title()

    def add_listener(self, listener: Callable[[int], None]) -> None:
        """Registra una función que recibe la cantidad de transferencias activas.

        Args:
            listener (Callable[[int], None]): Recibe el número de filas en curso o en cola.
        """
        self._listeners.append(listener)

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

    def add_job(self, job: DownloadJob) -> None:
        """Agrega una descarga.

        Args:
            job (DownloadJob): Descarga en cola.
        """
        self.add_row(job.id, job.entry.name, "download")

    def add_row(self, row_id: str, name: str, icon: str) -> None:
        """Agrega una transferencia en cola.

        Args:
            row_id (str): Identificador de la fila.
            name (str): Archivo o carpeta.
            icon (str): ``"download"`` o ``"upload"``.
        """
        if not self._rows:
            self._separator.pack(fill="x")
            self._list.pack(fill="both", expand=True)
        row = TransferRow(self._list.inner, self._theme, name, icon)
        row.pack(fill="x")
        self._rows[row_id] = row
        self._update_title()

    def set_status(self, row_id: str, text: str) -> None:
        """Muestra un estado de espera (por ejemplo, «En cola (reintento)»).

        Args:
            row_id (str): Identificador de la fila.
            text (str): Texto de la píldora.
        """
        self.set_state(row_id, "wait", text)

    def set_state(self, row_id: str, kind: str, label: str, detail: str = "",
                  active: bool | None = None) -> None:
        """Muestra el estado de una fila con su píldora.

        Args:
            row_id (str): Identificador de la fila.
            kind (str): ``"wait"``, ``"run"``, ``"ok"``, ``"warn"`` o ``"bad"``.
            label (str): Texto de la píldora.
            detail (str): Motivo o resultado.
            active (bool | None): Si sigue en curso; ``None`` = según el tipo de píldora.
        """
        if row := self._rows.get(row_id):
            row.set_state(kind, label, detail, active)
            self._update_title()

    def set_progress(self, row_id: str, done: int, total: int, speed: str,
                     eta: str) -> None:
        """Muestra el avance de una fila.

        Args:
            row_id (str): Identificador de la fila.
            done (int): Bytes transferidos.
            total (int): Bytes totales.
            speed (str): Velocidad ya formateada.
            eta (str): Tiempo restante ya formateado.
        """
        if row := self._rows.get(row_id):
            row.set_progress(transfer_progress(done, total), speed, eta)
            self._update_title()

    def update_job(self, job: DownloadJob, speed: float, current_file: str,
                   eta: float | None = None) -> None:
        """Actualiza el avance de una descarga.

        Args:
            job (DownloadJob): Descarga en curso.
            speed (float): Velocidad en bytes por segundo.
            current_file (str): Archivo que se está descargando (no se muestra en la fila).
            eta (float | None): Segundos restantes estimados.
        """
        self.set_progress(job.id, job.done_bytes, job.total_bytes,
                          presenters.speed_text(speed), format_eta(eta))

    def finish_job(self, job: DownloadJob, result: DownloadResult) -> None:
        """Muestra el resultado de una descarga.

        Args:
            job (DownloadJob): Descarga terminada.
            result (DownloadResult): Resultado.
        """
        self.set_state(job.id, *download_result_status(result))

    def _update_title(self) -> None:
        """Actualiza el contador del título y avisa cuántas siguen activas."""
        self._title.configure(text=f"Transferencias · {len(self._rows)}" if self._rows
                              else "Transferencias")
        active = sum(1 for row in self._rows.values() if row.is_active)
        for listener in self._listeners:
            listener(active)
