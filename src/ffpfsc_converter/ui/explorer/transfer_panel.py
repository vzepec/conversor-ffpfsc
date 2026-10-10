"""Panel de descargas: carpeta de destino, tabla de progreso y botones."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.domain.remote import DownloadJob, DownloadResult
from ffpfsc_converter.ui.explorer import presenters

_COLUMNS = (
    ("item", "Descarga", 330, "w"),
    ("progress", "Progreso", 250, "w"),
    ("speed", "Velocidad", 100, "e"),
    ("status", "Estado", 260, "w"),
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
    ) -> None:
        """Crea el panel.

        Args:
            parent (tk.Misc): Contenedor.
            on_change_destination (Callable[[], None]): Botón "Cambiar…".
            on_cancel (Callable[[], None]): Botón "Cancelar descargas".
            on_open_destination (Callable[[], None]): Botón "Abrir carpeta".
        """
        super().__init__(parent)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 4))
        # Los botones se empaquetan primero para que una ruta larga no los aplaste.
        ttk.Button(bar, text="Abrir carpeta", command=on_open_destination).pack(side="right")
        self._cancel = ttk.Button(bar, text="■ Cancelar descargas", command=on_cancel,
                                  state="disabled")
        self._cancel.pack(side="right", padx=6)
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

    def add_job(self, job: DownloadJob) -> None:
        """Agrega una descarga a la tabla.

        Args:
            job (DownloadJob): Descarga en cola.
        """
        self._tree.insert("", "end", iid=job.id, values=(
            presenters.entry_label(job.entry), "", "", "En cola"))

    def update_job(self, job: DownloadJob, speed: float, current_file: str) -> None:
        """Actualiza el progreso de una descarga.

        Args:
            job (DownloadJob): Descarga en curso.
            speed (float): Velocidad en bytes por segundo.
            current_file (str): Archivo que se está descargando.
        """
        self._set(job.id, progress=presenters.progress_text(job),
                  speed=presenters.speed_text(speed), status=f"Descargando {current_file}")

    def finish_job(self, job: DownloadJob, result: DownloadResult) -> None:
        """Muestra el resultado de una descarga.

        Args:
            job (DownloadJob): Descarga terminada.
            result (DownloadResult): Resultado.
        """
        self._set(job.id, progress=presenters.progress_text(job), speed="",
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
