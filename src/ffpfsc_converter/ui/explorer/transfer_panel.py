"""Panel de transferencias: descargas y subidas con su avance, velocidad y tiempo restante."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.domain.remote import DownloadJob, DownloadResult
from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.ui.explorer import presenters
from ffpfsc_converter.ui.explorer.transfer_header import TransferActions, TransferHeader
from ffpfsc_converter.ui.explorer.transfer_presenters import (
    download_result_status,
    transfer_progress,
)
from ffpfsc_converter.ui.explorer.transfer_row import TransferRow
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.scroll_frame import ScrollFrame

#: Alto máximo de la lista (píxeles lógicos); con más filas aparece la barra de desplazamiento.
_MAX_LIST_HEIGHT = 220
_SCROLL_DELAY_MS = 60


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
        self._header = TransferHeader(self, theme, actions)
        self._header.pack(fill="x")
        self._separator = ttk.Separator(self)
        self._list = ScrollFrame(self, theme)
        self._list.pack_propagate(False)
        self._list.inner.bind("<Configure>", lambda _e: self._fit_height(), add="+")
        self.refresh()

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
        self._header.set_destination(folder)

    def set_running(self, running: bool) -> None:
        """Habilita "Cancelar" solo mientras hay descargas.

        Args:
            running (bool): ``True`` si hay descargas en curso.
        """
        self._header.set_running(running)

    def set_retry_enabled(self, enabled: bool) -> None:
        """Habilita "Reintentar fallidas" solo si hay transferencias fallidas.

        Args:
            enabled (bool): ``True`` si hay algo que reintentar.
        """
        self._header.set_retry_enabled(enabled)

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
            icon (str): ``"download"``, ``"upload"`` o ``"replace"``.
        """
        if not self._rows:
            self._separator.pack(fill="x")
            self._list.pack(fill="both", expand=True)
        row = TransferRow(self._list.inner, self._theme, name, icon)
        row.pack(fill="x")
        self._rows[row_id] = row
        self.after(_SCROLL_DELAY_MS, self._list.scroll_to_end)
        self.refresh()

    def _fit_height(self) -> None:
        """Ajusta el alto de la lista a sus filas, hasta el máximo permitido."""
        wanted = self._list.inner.winfo_reqheight()
        self._list.configure(height=min(wanted, self._theme.metrics.px(_MAX_LIST_HEIGHT)))

    def row(self, row_id: str) -> TransferRow | None:
        """Obtiene una fila para actualizarla directamente.

        Args:
            row_id (str): Identificador de la fila.

        Returns:
            TransferRow | None: La fila, o ``None`` si no existe.
        """
        return self._rows.get(row_id)

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
            self.refresh()

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
            self.refresh()

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

    def remove_finished(self) -> list[str]:
        """Quita las filas que ya no están en cola ni en curso.

        Returns:
            list[str]: Identificadores de las filas quitadas.
        """
        finished = [row_id for row_id, row in self._rows.items() if not row.is_active]
        for row_id in finished:
            self._rows.pop(row_id).destroy()
        if not self._rows:
            self._list.pack_forget()
            self._separator.pack_forget()
        self.refresh()
        return finished

    def refresh(self) -> None:
        """Actualiza el contador del título y avisa cuántas siguen activas."""
        active = sum(1 for row in self._rows.values() if row.is_active)
        self._header.show_counts(len(self._rows), len(self._rows) - active)
        for listener in self._listeners:
            listener(active)
