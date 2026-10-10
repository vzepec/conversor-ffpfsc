"""Panel de descargas: carpeta de destino, tabla de progreso y botones."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.domain.remote import DownloadJob, DownloadResult
from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.ui.explorer import presenters

_COLUMNS = (
    ("item", "Transferencia", 330, "w"),
    ("progress", "Progreso", 250, "w"),
    ("speed", "Velocidad", 100, "e"),
    ("eta", "Restante", 150, "w"),
    ("status", "Estado", 230, "w"),
)
_NO_DESTINATION = "(elige una carpeta)"


class TransferPanel(ttk.Frame):
    """Cola de descargas desde la PS5."""

    def __init__(
        self,
        parent: tk.Misc,
        on_change_destination: Callable[[], None],
        on_cancel: Callable[[], None],
        on_open_destination: Callable[[], None],
        on_retry_failed: Callable[[], None],
    ) -> None:
        """Crea el panel.

        Args:
            parent (tk.Misc): Contenedor.
            on_change_destination (Callable[[], None]): Botón "Cambiar…".
            on_cancel (Callable[[], None]): Botón "Cancelar descargas".
            on_open_destination (Callable[[], None]): Botón "Abrir carpeta".
            on_retry_failed (Callable[[], None]): Botón "Reintentar fallidas".
        """
        super().__init__(parent)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 4))
        # Los botones se empaquetan primero para que una ruta larga no los aplaste.
        ttk.Button(bar, text="Abrir carpeta", command=on_open_destination).pack(side="right")
        self._cancel = ttk.Button(bar, text="■ Cancelar descargas", command=on_cancel,
                                  state="disabled")
        self._cancel.pack(side="right", padx=6)
        self._retry = ttk.Button(bar, text="↻ Reintentar fallidas", command=on_retry_failed,
                                 state="disabled")
        self._retry.pack(side="right")
        ttk.Label(bar, text="Descargar en:").pack(side="left")
        ttk.Button(bar, text="Cambiar…", command=on_change_destination).pack(side="right")
        self._destination = ttk.Label(bar, text=_NO_DESTINATION)
        self._destination.pack(side="left", padx=6, fill="x", expand=True)
        self._tree = ttk.Treeview(self, columns=[c[0] for c in _COLUMNS], show="headings",
                                  height=4)
        for col_id, heading, width, anchor in _COLUMNS:
            self._tree.heading(col_id, text=heading)
            self._tree.column(col_id, width=width, anchor=anchor)
        self._tree.pack(fill="both", expand=True)

    def set_destination(self, folder: Path | None) -> None:
        """Muestra la carpeta de destino.

        Args:
            folder (Path | None): Carpeta elegida, o ``None`` si aún no hay.
        """
        self._destination.configure(text=str(folder) if folder else _NO_DESTINATION)

    def set_running(self, running: bool) -> None:
        """Habilita "Cancelar" solo mientras hay descargas.

        Args:
            running (bool): ``True`` si hay descargas en curso.
        """
        self._cancel.configure(state="normal" if running else "disabled")

    def set_retry_enabled(self, enabled: bool) -> None:
        """Habilita "Reintentar fallidas" solo si hay transferencias fallidas.

        Args:
            enabled (bool): ``True`` si hay algo que reintentar.
        """
        self._retry.configure(state="normal" if enabled else "disabled")

    def set_status(self, row_id: str, status: str) -> None:
        """Cambia solo el estado de una fila (por ejemplo, un aviso de reintento).

        Args:
            row_id (str): Identificador de la fila.
            status (str): Texto de estado.
        """
        self._set(row_id, status=status)

    def add_job(self, job: DownloadJob) -> None:
        """Agrega una descarga a la tabla.

        Args:
            job (DownloadJob): Descarga en cola.
        """
        self.add_row(job.id, presenters.entry_label(job.entry))

    def add_row(self, row_id: str, label: str) -> None:
        """Agrega una transferencia (descarga o subida) en cola.

        Args:
            row_id (str): Identificador de la fila.
            label (str): Texto de la columna "Descarga".
        """
        self._tree.insert("", "end", iid=row_id, values=(label, "", "", "", "En cola"))

    def update_row(self, row_id: str, progress: str, speed: str, status: str,
                   eta: str = "") -> None:
        """Actualiza una fila cualquiera.

        Args:
            row_id (str): Identificador de la fila.
            progress (str): Texto de progreso.
            speed (str): Velocidad.
            status (str): Estado.
            eta (str): Tiempo restante ya formateado.
        """
        self._set(row_id, progress=progress, speed=speed, status=status, eta=eta)

    def update_job(self, job: DownloadJob, speed: float, current_file: str,
                   eta: float | None = None) -> None:
        """Actualiza el progreso de una descarga.

        Args:
            job (DownloadJob): Descarga en curso.
            speed (float): Velocidad en bytes por segundo.
            current_file (str): Archivo que se está descargando.
            eta (float | None): Segundos restantes estimados.
        """
        self._set(job.id, progress=presenters.progress_text(job),
                  speed=presenters.speed_text(speed), eta=format_eta(eta),
                  status=f"Descargando {current_file}")

    def finish_job(self, job: DownloadJob, result: DownloadResult) -> None:
        """Muestra el resultado de una descarga.

        Args:
            job (DownloadJob): Descarga terminada.
            result (DownloadResult): Resultado.
        """
        self._set(job.id, progress=presenters.progress_text(job), speed="", eta="",
                  status=presenters.download_result_text(result))

    def _set(self, row: str, **values: str) -> None:
        """Cambia varias celdas de una fila si existe.

        Args:
            row (str): Identificador de la fila.
            **values (str): Columna → texto.
        """
        if self._tree.exists(row):
            for column, text in values.items():
                self._tree.set(row, column, text)
