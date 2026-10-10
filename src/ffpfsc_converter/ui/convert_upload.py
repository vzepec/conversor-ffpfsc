"""Subida a la PS5 de los juegos comprimidos en la pestaña Convertir.

Reutiliza la subida de la pestaña PS5 (``.part`` verificado, reintentos y ETA).
Si no hay conexión, la ofrece (o explica cómo vincular la consola) y deja la
subida en espera hasta conectar.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.domain.models import ConversionJob, JobState
from ffpfsc_converter.domain.pipeline_events import UploadFinished, UploadProgress
from ffpfsc_converter.domain.remote_events import TransferRetrying
from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.infrastructure.settings_store import load_settings
from ffpfsc_converter.ui import dialogs, job_table
from ffpfsc_converter.ui.explorer import presenters as remote_text
from ffpfsc_converter.ui.explorer.controller import ExplorerController
from ffpfsc_converter.ui.main_view import MainView
from ffpfsc_converter.ui.upload_dialog import UploadDestinationDialog

_PAIRING_STEPS = (
    "Para subir juegos hay que vincular la PS5 una sola vez:\n\n"
    "1. Carga el payload de ps5upload en la PS5 (carpeta payload/ del proyecto).\n"
    "2. En la pestaña PS5 escribe la IP de la consola y pulsa «Conectar».\n"
    "3. Escribe el código de 6 dígitos que muestra la PS5.\n\n"
    "La subida empezará sola en cuanto se conecte. ¿Ir a la pestaña PS5 ahora?"
)


class ConvertedUploader:
    """Botón "Subir a la PS5" de la pestaña Convertir."""

    def __init__(self, view: MainView, explorer: ExplorerController,
                 jobs: Callable[[], list[ConversionJob]],
                 show_ps5_tab: Callable[[], None]) -> None:
        """Prepara el subidor.

        Args:
            view (MainView): Vista de la pestaña Convertir.
            explorer (ExplorerController): Controlador de la pestaña PS5.
            jobs (Callable[[], list[ConversionJob]]): Devuelve los trabajos de conversión.
            show_ps5_tab (Callable[[], None]): Cambia a la pestaña PS5.
        """
        self._view, self._explorer = view, explorer
        self._jobs, self._show_ps5_tab = jobs, show_ps5_tab
        self._status: dict[str, str] = {}  # id de trabajo → "pending" | "uploading" | "done"

    def refresh(self) -> None:
        """Habilita el botón si hay juegos comprimidos pendientes de subir."""
        self._view.set_upload_enabled(bool(self._eligible()))

    def upload(self) -> None:
        """Pide el destino y sube los juegos elegidos (conectando si hace falta)."""
        jobs = self._eligible()
        selected = self._view.table.selected_ids()
        jobs = [j for j in jobs if j.id in selected] or jobs
        if not jobs:
            dialogs.show_info("No hay juegos comprimidos pendientes de subir.")
            return
        remote_dir = UploadDestinationDialog(self._view.table,
                                             [j.output.name for j in jobs]).ask()
        if remote_dir is None or not self._ensure_connection():
            return
        for job in jobs:
            self._status[job.id] = "pending"
            self._set(job, "⬆ Esperando conexión con la PS5…")
        self._explorer.when_connected(lambda: self._start(jobs, remote_dir))
        self.refresh()

    def _ensure_connection(self) -> bool:
        """Comprueba la conexión y, si no hay, ofrece conectar o explica cómo vincular.

        Returns:
            bool: ``True`` si se puede continuar (ya conectado o se conectará).
        """
        if self._explorer.target is not None:
            return True
        host = str(load_settings().get("ps5_host", ""))
        if host:
            if not dialogs.confirm(f"No hay conexión con la PS5 ({host}). ¿Conectar ahora y "
                                   "subir? La subida empezará en cuanto se conecte."):
                return False
            self._explorer.connect()
            return True
        if dialogs.confirm(_PAIRING_STEPS):
            self._show_ps5_tab()
        return True

    def _start(self, jobs: list[ConversionJob], remote_dir: str) -> None:
        """Inicia las subidas (ya hay conexión) y sigue su avance en las filas.

        Args:
            jobs (list[ConversionJob]): Juegos a subir.
            remote_dir (str): Carpeta remota de destino.
        """
        ids = self._explorer.modify.upload_paths([j.output for j in jobs], remote_dir)
        if not ids:  # había otra operación en curso: se pueden reintentar después
            for job in jobs:
                self._status.pop(job.id, None)
                self._set(job, "✖ No se subió (PS5 ocupada); vuelve a intentarlo")
            self.refresh()
            return
        for job, upload_id in zip(jobs, ids, strict=True):
            self._status[job.id] = "uploading"
            self._explorer.upload_listeners[upload_id] = (
                lambda event, job=job: self._on_event(job, event))

    def _on_event(self, job: ConversionJob, event: object) -> None:
        """Refleja en la fila del juego el avance de su subida.

        Args:
            job (ConversionJob): Juego que se está subiendo.
            event (object): ``UploadProgress``, ``TransferRetrying`` o ``UploadFinished``.
        """
        if isinstance(event, UploadProgress):
            parts = [remote_text.upload_progress_text(event.done, event.total),
                     remote_text.speed_text(event.bytes_per_second),
                     format_eta(event.eta_seconds)]
            self._set(job, "⬆ Subiendo a la PS5: " + "  —  ".join(p for p in parts if p))
        elif isinstance(event, TransferRetrying):
            self._set(job, f"⚠ Reintentando la subida ({event.attempt} de "
                           f"{event.max_attempts})…")
        elif isinstance(event, UploadFinished):
            done = event.succeeded
            self._status[job.id] = "done" if done else "failed"
            self._set(job, f"✔ En la PS5: {event.message}" if done
                      else f"✖ No se subió: {event.message}")
            self.refresh()

    def _eligible(self) -> list[ConversionJob]:
        """Obtiene los juegos comprimidos con éxito que aún no se subieron.

        Returns:
            list[ConversionJob]: Juegos que se pueden subir.
        """
        busy = {"pending", "uploading", "done"}
        return [j for j in self._jobs() if j.state is JobState.SUCCEEDED
                and j.output.is_file() and self._status.get(j.id) not in busy]

    def _set(self, job: ConversionJob, text: str) -> None:
        """Escribe el estado de la subida en la fila del juego.

        Args:
            job (ConversionJob): Juego.
            text (str): Texto de estado.
        """
        self._view.table.set_cell(job.id, job_table.STATUS, text)


def tab_selector(notebook: ttk.Notebook, tab: tk.Misc) -> Callable[[], None]:
    """Crea una función que muestra una pestaña.

    Args:
        notebook (ttk.Notebook): Contenedor de pestañas.
        tab (tk.Misc): Pestaña a mostrar.

    Returns:
        Callable[[], None]: Función sin argumentos que selecciona la pestaña.
    """
    return lambda: notebook.select(tab)
