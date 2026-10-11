"""Controlador de la vista Convertir: cola de juegos, opciones y conversión.

Traduce las acciones del usuario (recibidas de :class:`MainView`) en llamadas
a los servicios y aplica sobre la vista los eventos de la conversión.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from ffpfsc_converter.config import PRESETS
from ffpfsc_converter.domain.events import Event, EventSink, JobProgress, LogMessage
from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions
from ffpfsc_converter.errors import ConverterError
from ffpfsc_converter.infrastructure.system import open_in_file_manager
from ffpfsc_converter.services.analysis import start_analysis
from ffpfsc_converter.services.conversion import ConversionRunner
from ffpfsc_converter.services.discovery import create_job, output_path_for
from ffpfsc_converter.services.preflight import check_free_space
from ffpfsc_converter.ui import dialogs, presenters
from ffpfsc_converter.ui import job_presenters as jp
from ffpfsc_converter.ui.convert_upload import ConvertedUploader
from ffpfsc_converter.ui.event_handlers import ViewUpdater
from ffpfsc_converter.ui.explorer.controller import ExplorerController
from ffpfsc_converter.ui.job_presenters import READY_DETAIL, READY_LABEL
from ffpfsc_converter.ui.main_view import MainView, ViewCallbacks
from ffpfsc_converter.ui.preferences import save_output_dir
from ffpfsc_converter.ui.theme import ThemeManager

_ESTIMATE_LEVELS = sorted({p.level for p in PRESETS})


@dataclass(frozen=True)
class ConvertLinks:
    """Lo que la vista Convertir necesita del resto de la ventana.

    Attributes:
        explorer (ExplorerController): Vista PS5 (para subir los juegos convertidos).
        on_queue_changed (Callable[[int], None]): Recibe la cantidad de juegos en la cola.
        show_ps5 (Callable[[], None]): Muestra la vista PS5.
    """

    explorer: ExplorerController
    on_queue_changed: Callable[[int], None]
    show_ps5: Callable[[], None]


class ConvertController:
    """Coordina la vista Convertir con la cola de trabajos y el conversor.

    Attributes:
        jobs (list[ConversionJob]): Juegos de la cola, en orden.
        runner (ConversionRunner): Conversión en segundo plano.
        view (MainView): Vista Convertir.
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager, emit: EventSink,
                 links: ConvertLinks) -> None:
        """Crea la vista y el subidor a la PS5.

        Args:
            parent (tk.Misc): Contenedor de la vista.
            theme (ThemeManager): Tema.
            emit (EventSink): Cola de eventos de la ventana.
            links (ConvertLinks): Vista PS5 y ganchos de la ventana principal.
        """
        self.jobs: list[ConversionJob] = []
        self.runner = ConversionRunner(emit)
        self._emit, self._on_queue_changed = emit, links.on_queue_changed
        self.view = MainView(parent, theme, self._callbacks())
        self._output_dir = self.view.options.output_dir
        self._updater = ViewUpdater(self.view)
        self._uploader = ConvertedUploader(self.view, links.explorer, lambda: self.jobs,
                                           links.show_ps5)

    def _callbacks(self) -> ViewCallbacks:
        """Reúne las acciones de la vista Convertir.

        Returns:
            ViewCallbacks: Acciones conectadas a este controlador.
        """
        return ViewCallbacks(
            on_paths=self.add_paths, on_pick_folder=self.pick_folder,
            on_pick_file=self.pick_file, on_output_changed=self.set_output_dir,
            on_preset_changed=self._refresh_estimates, on_start=self.start,
            on_cancel=self.cancel, on_remove=self.remove_selected,
            on_open_output=self.open_output,
            on_upload_all=lambda: self._uploader.upload_all(),
            on_upload_row=lambda row_id: self._uploader.upload_ids({row_id}),
        )

    def handle(self, event: Event) -> None:
        """Aplica un evento de la conversión sobre la vista.

        Args:
            event (Event): Evento publicado por un servicio de conversión.
        """
        self._updater.handle(event)
        if not isinstance(event, (JobProgress, LogMessage)):  # el avance no cambia la cola
            self.refresh_queue()

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

    def set_output_dir(self, folder: Path | None) -> None:
        """Aplica una carpeta de destino nueva a los trabajos pendientes y la recuerda.

        Args:
            folder (Path | None): Carpeta elegida, o ``None`` para guardar junto a cada juego.
        """
        self._output_dir = folder
        save_output_dir(folder)
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
        if self.runner.is_running:
            dialogs.show_info("Espera a que termine la conversión actual.")
            return
        try:
            job = create_job(path, self._output_dir)
        except ConverterError as exc:
            dialogs.show_error(str(exc))
            return
        if any(j.game_root == job.game_root and (j.is_queued or j.already_compressed)
               for j in self.jobs):
            return
        self.jobs.append(job)
        self.view.table.add_row(job.id, "Leyendo…", presenters.source_display_name(job))
        if job.already_compressed:
            self.view.table.set_status(job.id, "ok", READY_LABEL, READY_DETAIL)
        self.refresh_queue()
        if job.game_root != path:
            self.view.write_log(f"Juego detectado en: {job.game_root}")
        start_analysis(job, _ESTIMATE_LEVELS, self._emit)

    def remove_selected(self) -> None:
        """Quita de la cola los trabajos seleccionados (salvo durante una conversión)."""
        if self.runner.is_running:
            return
        selected = self.view.table.selected_ids()
        self.jobs = [j for j in self.jobs if j.id not in selected]
        self.view.table.delete_rows(selected)
        self.refresh_queue()

    def open_output(self) -> None:
        """Abre la carpeta de destino (o la del último juego) en el gestor de archivos."""
        target = self._output_dir or (self.jobs[-1].output.parent if self.jobs else None)
        if target:
            open_in_file_manager(target)

    def start(self) -> None:
        """Confirma y lanza la conversión de todos los trabajos pendientes."""
        pending = self._queued_jobs()
        if not pending:
            dialogs.show_info("Agrega primero una carpeta de juego.")
            return
        options = self.view.options.conversion_options()
        if not all(self._confirm_job(job, options) for job in pending):
            return
        self.view.set_running(True)
        self.runner.start(pending, options)

    def cancel(self) -> None:
        """Pide cancelar la conversión en curso."""
        self.runner.cancel()
        self.view.set_status("Cancelando…")

    def refresh_queue(self) -> None:
        """Actualiza el resumen de la cola, el contador lateral y los botones de subida."""
        options = self.view.options
        self.view.set_summary(jp.queue_summary(self.jobs, options.selected_preset().level,
                                               options.is_performance()))
        self._on_queue_changed(len(self.jobs))
        self._uploader.refresh()

    def _queued_jobs(self) -> list[ConversionJob]:
        """Obtiene los trabajos pendientes de convertir.

        Returns:
            list[ConversionJob]: Trabajos en estado ``QUEUED``, en orden.
        """
        return [j for j in self.jobs if j.is_queued]

    def _confirm_job(self, job: ConversionJob, options: ConversionOptions) -> bool:
        """Pide confirmación si se va a sobrescribir o si puede faltar espacio.

        Args:
            job (ConversionJob): Trabajo a comprobar.
            options (ConversionOptions): Opciones elegidas (nivel y rendimiento).

        Returns:
            bool: ``True`` si se puede convertir el trabajo.
        """
        if job.output.exists() and not dialogs.confirm_overwrite(job.output):
            return False
        space = check_free_space(job, options)
        return space is None or space.is_enough or dialogs.confirm_low_space(space)

    def _refresh_estimates(self) -> None:
        """Actualiza el peso estimado de cada fila al cambiar el modo o el rendimiento."""
        options = self.view.options
        level, performance = options.selected_preset().level, options.is_performance()
        for job in self.jobs:
            self.view.table.set_sizes(job.id, jp.size_lines(job, level, performance))
        self.refresh_queue()
