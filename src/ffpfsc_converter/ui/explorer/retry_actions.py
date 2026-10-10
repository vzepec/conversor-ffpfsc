"""Reintento manual de las transferencias que fallaron tras los reintentos automáticos."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ffpfsc_converter.domain.remote import DownloadJob, DownloadResult, DownloadState
from ffpfsc_converter.ui import dialogs

if TYPE_CHECKING:  # evita la importación circular con el controlador
    from ffpfsc_converter.ui.explorer.controller import ExplorerController


class RetryActions:
    """Recuerda las descargas y subidas fallidas y las vuelve a encolar a pedido."""

    def __init__(self, controller: ExplorerController) -> None:
        """Empieza sin transferencias fallidas.

        Args:
            controller (ExplorerController): Controlador de la pestaña.
        """
        self._ctl = controller
        self._downloads: dict[str, DownloadJob] = {}
        self._uploads: dict[str, tuple[Path, str]] = {}
        self._pending_uploads: dict[str, tuple[Path, str]] = {}

    def register_upload(self, upload_id: str, local: Path, remote_dir: str) -> None:
        """Recuerda el origen y destino de una subida (por si hay que reintentarla).

        Args:
            upload_id (str): Fila de la subida.
            local (Path): Archivo local.
            remote_dir (str): Carpeta remota de destino.
        """
        self._pending_uploads[upload_id] = (local, remote_dir)

    def download_finished(self, job: DownloadJob, result: DownloadResult) -> None:
        """Registra el resultado de una descarga.

        Args:
            job (DownloadJob): Descarga terminada.
            result (DownloadResult): Resultado (las fallidas o canceladas se pueden reintentar).
        """
        if result.succeeded:
            self._downloads.pop(job.id, None)
        else:
            self._downloads[job.id] = job
        self._refresh_button()

    def upload_finished(self, upload_id: str, succeeded: bool) -> None:
        """Registra el resultado de una subida.

        Args:
            upload_id (str): Fila de la subida.
            succeeded (bool): ``True`` si quedó verificada en la PS5.
        """
        origin = self._pending_uploads.pop(upload_id, None)
        if succeeded:
            self._uploads.pop(upload_id, None)
        elif origin is not None:
            self._uploads[upload_id] = origin
        self._refresh_button()

    def retry_failed(self) -> None:
        """Vuelve a encolar las descargas fallidas o, si no hay, las subidas fallidas."""
        target = self._ctl.target
        if target is None:
            dialogs.show_error("No hay conexión con la PS5. Pulsa «Conectar» y reintenta.")
            return
        if self._ctl.downloads.is_running or self._ctl.modify.busy:
            dialogs.show_info("Espera a que termine la operación en curso.")
            return
        if self._downloads:
            jobs = list(self._downloads.values())
            self._downloads.clear()
            for job in jobs:
                job.state, job.done_bytes = DownloadState.QUEUED, 0
                self._ctl.view.transfers.set_status(job.id, "En cola (reintento)")
            self._ctl.view.transfers.set_running(True)
            self._ctl.downloads.start(jobs, target)
        elif self._uploads:
            self._retry_uploads(target.host, target.port)
        self._refresh_button()

    def _retry_uploads(self, host: str, port: int) -> None:
        """Reintenta las subidas fallidas de una misma carpeta remota (la primera pendiente).

        Args:
            host (str): Dirección de la PS5.
            port (int): Puerto FTP.
        """
        remote_dir = next(iter(self._uploads.values()))[1]
        group = {uid: origin for uid, origin in self._uploads.items() if origin[1] == remote_dir}
        for upload_id, origin in group.items():
            del self._uploads[upload_id]
            self._pending_uploads[upload_id] = origin
            self._ctl.view.transfers.set_status(upload_id, "En cola (reintento)")
        self._ctl.modify.changes.upload(host, port, [o[0] for o in group.values()], remote_dir,
                                        ids=list(group))
        self._ctl.view.set_browsing_enabled(False)

    def _refresh_button(self) -> None:
        """Habilita "Reintentar fallidas" solo si queda algo por reintentar."""
        self._ctl.view.transfers.set_retry_enabled(bool(self._downloads or self._uploads))
