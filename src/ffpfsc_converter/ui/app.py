"""Controlador de la ventana principal.

Traduce las acciones del usuario (recibidas de :class:`MainView`) en llamadas
a los servicios. Los servicios publican eventos desde hilos de fondo en
``self._events``; :meth:`MainWindow._poll_events` los consume en el hilo de la
interfaz y los entrega a :class:`ViewUpdater`.
"""
from __future__ import annotations

import queue
from collections.abc import Iterable
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.config import APP_TITLE, PRESETS
from ffpfsc_converter.domain.events import Event, JobFinished, QueueFinished
from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions
from ffpfsc_converter.domain.remote_events import RemoteEvent
from ffpfsc_converter.errors import ConverterError
from ffpfsc_converter.infrastructure.system import open_in_file_manager
from ffpfsc_converter.services.analysis import start_analysis
from ffpfsc_converter.services.conversion import ConversionRunner
from ffpfsc_converter.services.discovery import create_job, output_path_for
from ffpfsc_converter.services.preflight import check_free_space
from ffpfsc_converter.ui import dialogs, job_table, presenters, theme
from ffpfsc_converter.ui.convert_upload import ConvertedUploader, tab_selector
from ffpfsc_converter.ui.dnd import create_root
from ffpfsc_converter.ui.event_handlers import ViewUpdater
from ffpfsc_converter.ui.explorer.controller import ExplorerController
from ffpfsc_converter.ui.explorer.updater import ExplorerUpdater
from ffpfsc_converter.ui.main_view import MainView, ViewCallbacks

_ESTIMATE_LEVELS = sorted({p.level for p in PRESETS})


class MainWindow:
    """Ventana principal: coordina la vista, la cola de trabajos y los servicios."""

    def __init__(self, initial_paths: Iterable[Path] = ()) -> None:
        """Crea la ventana y encola las rutas iniciales.

        Args:
            initial_paths (Iterable[Path]): Rutas recibidas por línea de comandos.
        """
        self.root = create_root()
        self.root.title(APP_TITLE)
        self.root.geometry(theme.WINDOW_SIZE)
        self.root.minsize(*theme.WINDOW_MIN_SIZE)

        self._jobs: list[ConversionJob] = []
        self._events: queue.Queue[Event | RemoteEvent] = queue.Queue()
        self._runner = ConversionRunner(self._events.put)
        self._output_dir: Path | None = None  # None = junto a cada juego
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        convert_tab, ps5_tab = ttk.Frame(notebook), ttk.Frame(notebook)
        notebook.add(convert_tab, text="  Convertir  ")
        notebook.add(ps5_tab, text="  PS5  ")
        self._explorer = ExplorerController(ps5_tab, self._events.put)
        self._explorer.view.pack(fill="both", expand=True)
        self._explorer_updater = ExplorerUpdater(self._explorer)
        self._view = MainView(convert_tab, ViewCallbacks(
            on_paths=self.add_paths, on_pick_folder=self.pick_folder,
            on_pick_file=self.pick_file, on_pick_output_dir=self.pick_output_dir,
            on_preset_changed=self._refresh_estimates, on_start=self.start,
            on_cancel=self.cancel, on_remove=self.remove_selected,
            on_open_output=self.open_output, on_upload_ps5=lambda: self._uploader.upload(),
        ))
        self._updater = ViewUpdater(self._view)
        self._uploader = ConvertedUploader(self._view, self._explorer, lambda: self._jobs,
                                           tab_selector(notebook, ps5_tab))
        self.root.after(theme.EVENT_POLL_MS, self._poll_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.add_paths(initial_paths)

    def run(self) -> None:
        """Inicia el bucle principal de Tkinter hasta que se cierra la ventana."""
        self.root.mainloop()

    def pick_folder(self) -> None:
        """Pide una carpeta de juego y la encola."""
        folder = dialogs.ask_game_folder()
        if folder:
            self.add_path(folder)

    def pick_file(self) -> None:
        """Pide una imagen de juego y la encola."""
        file = dialogs.ask_game_image()
        if file:
            self.add_path(file)

    def pick_output_dir(self) -> None:
        """Pide la carpeta de destino y la aplica a los trabajos pendientes."""
        folder = dialogs.ask_output_dir()
        if not folder:
            return
        self._output_dir = folder
        self._view.options.set_output_dir(folder)
        for job in self._queued_jobs():
            job.output = output_path_for(job.source, folder)

    def add_paths(self, paths: Iterable[Path]) -> None:
        """Encola varias rutas.

        Args:
            paths (Iterable[Path]): Carpetas o imágenes a encolar.
        """
        for path in paths:
            self.add_path(path)

    def add_path(self, path: Path) -> None:
        """Crea un trabajo para la ruta, lo muestra y lanza su análisis.

        Muestra un error si la ruta no es un juego válido e ignora los juegos
        que ya están en la cola.

        Args:
            path (Path): Carpeta o imagen agregada por el usuario.
        """
        if self._runner.is_running:
            dialogs.show_info("Espera a que termine la conversión actual.")
            return
        try:
            job = create_job(path, self._output_dir)
        except ConverterError as exc:
            dialogs.show_error(str(exc))
            return
        if any(j.game_root == job.game_root for j in self._queued_jobs()):
            return
        self._jobs.append(job)
        self._view.table.add_row(job.id, {
            job_table.TITLE: "leyendo…",
            job_table.SOURCE: presenters.source_display_name(job),
            job_table.SIZE: "calculando…",
            job_table.ESTIMATE: presenters.PENDING_TEXT,
            job_table.STATUS: presenters.QUEUED_TEXT,
        })
        if job.game_root != path:
            self._view.write_log(f"Juego detectado en: {job.game_root}")
        start_analysis(job, _ESTIMATE_LEVELS, self._events.put)

    def remove_selected(self) -> None:
        """Quita de la cola los trabajos seleccionados (salvo durante una conversión)."""
        if self._runner.is_running:
            return
        selected = self._view.table.selected_ids()
        self._jobs = [j for j in self._jobs if j.id not in selected]
        self._view.table.delete_rows(selected)

    def open_output(self) -> None:
        """Abre la carpeta de destino (o la del último juego) en el gestor de archivos."""
        target = self._output_dir or (self._jobs[-1].output.parent if self._jobs else None)
        if target:
            open_in_file_manager(target)

    def start(self) -> None:
        """Confirma y lanza la conversión de todos los trabajos pendientes."""
        pending = self._queued_jobs()
        if not pending:
            dialogs.show_info("Agrega primero una carpeta de juego.")
            return
        options = self._view.options
        level = options.selected_preset().level
        if not all(self._confirm_job(job, level) for job in pending):
            return
        self._view.set_running(True)
        self._runner.start(pending, ConversionOptions(
            compression_level=level,
            cpu_count=options.cpu_count(),
            full_verify=options.full_verify(),
        ))

    def cancel(self) -> None:
        """Pide cancelar la conversión en curso."""
        self._runner.cancel()
        self._view.set_status("Cancelando…")

    def _on_close(self) -> None:
        """Cierra la ventana, cancelando antes la conversión si el usuario acepta."""
        if self._runner.is_running and not dialogs.confirm_quit_while_running():
            return
        if self._explorer.downloads.is_running and not dialogs.confirm_quit_while_downloading():
            return
        self._explorer.downloads.cancel()
        self._runner.cancel()
        self.root.destroy()

    def _poll_events(self) -> None:
        """Entrega a la vista los eventos pendientes y se vuelve a programar."""
        try:
            while True:
                event = self._events.get_nowait()
                if self._explorer_updater.handles(event):
                    self._explorer_updater.handle(event)
                else:
                    self._updater.handle(event)
                    if isinstance(event, (JobFinished, QueueFinished)):
                        self._uploader.refresh()
        except queue.Empty:
            pass
        self.root.after(theme.EVENT_POLL_MS, self._poll_events)

    def _queued_jobs(self) -> list[ConversionJob]:
        """Obtiene los trabajos pendientes de convertir.

        Returns:
            list[ConversionJob]: Trabajos en estado ``QUEUED``, en orden.
        """
        return [j for j in self._jobs if j.is_queued]

    def _confirm_job(self, job: ConversionJob, level: int) -> bool:
        """Pide confirmación si se va a sobrescribir o si puede faltar espacio.

        Args:
            job (ConversionJob): Trabajo a comprobar.
            level (int): Nivel de compresión elegido.

        Returns:
            bool: ``True`` si se puede convertir el trabajo.
        """
        if job.output.exists() and not dialogs.confirm_overwrite(job.output):
            return False
        space = check_free_space(job, level)
        return space is None or space.is_enough or dialogs.confirm_low_space(space)

    def _refresh_estimates(self) -> None:
        """Actualiza la columna de peso estimado al cambiar el modo."""
        level = self._view.options.selected_preset().level
        for job in self._jobs:
            self._view.table.set_cell(job.id, job_table.ESTIMATE,
                                      presenters.estimate_text(job, level))
