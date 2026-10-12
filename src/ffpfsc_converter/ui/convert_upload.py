"""Subida a la PS5 de los juegos comprimidos en la vista Convertir.

Reutiliza la subida de la vista PS5 (``.part`` verificado, reintentos y ETA).
Si no hay conexión, la ofrece (o explica cómo vincular la consola) y deja la
subida en espera hasta conectar.
"""
from __future__ import annotations

from collections.abc import Callable, Collection

from ffpfsc_converter.domain.models import ConversionJob, JobState
from ffpfsc_converter.domain.pipeline_events import UploadFinished, UploadProgress
from ffpfsc_converter.domain.remote_events import TransferRetrying
from ffpfsc_converter.infrastructure.settings_store import load_settings
from ffpfsc_converter.ui import dialogs
from ffpfsc_converter.ui import job_presenters as jp
from ffpfsc_converter.ui.explorer import presenters as remote_text
from ffpfsc_converter.ui.explorer.controller import ExplorerController
from ffpfsc_converter.ui.main_view import MainView
from ffpfsc_converter.ui.upload_dialog import UploadDestinationDialog

_PAIRING_STEPS = (
    "Para subir juegos hay que vincular la PS5 una sola vez:\n\n"
    "1. Carga el payload de ps5upload en la PS5 (carpeta payload/ del proyecto).\n"
    "2. En la sección PS5 escribe la IP de la consola y pulsa «Conectar».\n"
    "3. Escribe el código de 6 dígitos que muestra la PS5.\n\n"
    "La subida empezará sola en cuanto se conecte. ¿Ir a la sección PS5 ahora?"
)


class ConvertedUploader:
    """Botones "Subir a la PS5" (por fila) y "Subir completados a la PS5" de Convertir."""

    def __init__(self, view: MainView, explorer: ExplorerController,
                 jobs: Callable[[], list[ConversionJob]],
                 show_ps5: Callable[[], None]) -> None:
        """Prepara el subidor.

        Args:
            view (MainView): Vista Convertir.
            explorer (ExplorerController): Controlador de la vista PS5.
            jobs (Callable[[], list[ConversionJob]]): Devuelve los trabajos de conversión.
            show_ps5 (Callable[[], None]): Muestra la vista PS5.
        """
        self._view, self._explorer = view, explorer
        self._jobs, self._show_ps5 = jobs, show_ps5
        self._status: dict[str, str] = {}  # id de trabajo → "pending" | "uploading" | "done"

    def refresh(self) -> None:
        """Muestra el botón de cada fila subible y habilita el general si hay alguna."""
        eligible = {j.id for j in self._eligible()}
        for job in self._jobs():
            self._view.table.set_action(job.id, job.id in eligible)
        self._view.set_upload_enabled(bool(eligible))

    def upload_all(self) -> None:
        """Sube todos los juegos comprimidos que aún no están en la PS5."""
        self._upload(self._eligible())

    def upload_ids(self, ids: Collection[str]) -> None:
        """Sube los juegos indicados (si siguen pendientes de subir).

        Args:
            ids (Collection[str]): Identificadores de los trabajos.
        """
        self._upload([j for j in self._eligible() if j.id in ids])

    def _upload(self, jobs: list[ConversionJob]) -> None:
        """Pide el destino y sube los juegos (conectando si hace falta).

        Args:
            jobs (list[ConversionJob]): Juegos a subir.
        """
        if not jobs:
            dialogs.show_info("No hay juegos comprimidos pendientes de subir.")
            return
        remote_dir = UploadDestinationDialog(self._view.table, self._explorer.theme,
                                             [j.output.name for j in jobs]).ask()
        if remote_dir is None or not self._ensure_connection():
            return
        for job in jobs:
            self._status[job.id] = "pending"
            self._set(job, "wait", "Esperando conexión", "La subida empieza al conectar la PS5")
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
            self._show_ps5()
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
                self._set(job, "bad", "No se subió", "La PS5 estaba ocupada; vuelve a intentarlo")
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
            speed = remote_text.speed_text(event.bytes_per_second)
            (kind, label, detail), percent = jp.upload_status(
                event.done, event.total, speed, event.eta_seconds)
            self._set(job, kind, label, detail, percent)
        elif isinstance(event, TransferRetrying):
            self._set(job, "warn", f"Reintentando ({event.attempt} de {event.max_attempts})",
                      event.reason)
        elif isinstance(event, UploadFinished):
            done = event.succeeded
            self._status[job.id] = "done" if done else "failed"
            self._set(job, "ok" if done else "bad", "✓ En la PS5" if done else "No se subió",
                      event.message)
            self.refresh()

    def _eligible(self) -> list[ConversionJob]:
        """Obtiene los juegos comprimidos con éxito que aún no se subieron.

        Returns:
            list[ConversionJob]: Juegos que se pueden subir.
        """
        busy = {"pending", "uploading", "done"}
        return [j for j in self._jobs() if j.state is JobState.SUCCEEDED
                and j.output.exists() and self._status.get(j.id) not in busy]

    def _set(self, job: ConversionJob, kind: str, label: str, detail: str,
             percent: float | None = None) -> None:
        """Escribe el estado de la subida en la fila del juego.

        Args:
            job (ConversionJob): Juego.
            kind (str): Tipo de píldora (``"wait"``, ``"run"``, ``"ok"``…).
            label (str): Texto de la píldora.
            detail (str): Texto bajo la píldora.
            percent (float | None): Avance para la barra; ``None`` la oculta.
        """
        self._view.table.set_status(job.id, kind, label, detail, percent)
