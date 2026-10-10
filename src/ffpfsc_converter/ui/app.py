"""Ventana principal del conversor.

La ventana solo coordina: traduce acciones del usuario en llamadas a los
servicios y traduce los eventos de los servicios en cambios de widgets. Los
servicios publican eventos desde hilos de fondo en ``self._events``; la UI los
consume en su propio hilo con :meth:`MainWindow._poll_events`.
"""
from __future__ import annotations

import contextlib
import os
import queue
import tkinter as tk
from collections.abc import Callable, Iterable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ffpfsc_converter.config import APP_TITLE, DEFAULT_PRESET, FREE_SPACE_MARGIN, PRESETS
from ffpfsc_converter.domain.events import (
    Event,
    JobEstimateReady,
    JobFinished,
    JobInfoReady,
    JobProgress,
    JobSizeReady,
    JobStarted,
    LogMessage,
    QueueFinished,
)
from ffpfsc_converter.domain.models import CompressionPreset, ConversionJob, ConversionOptions
from ffpfsc_converter.errors import ConverterError
from ffpfsc_converter.infrastructure.system import open_in_file_manager
from ffpfsc_converter.services.analysis import start_analysis
from ffpfsc_converter.services.conversion import ConversionRunner
from ffpfsc_converter.services.discovery import create_job, output_path_for
from ffpfsc_converter.services.preflight import check_free_space
from ffpfsc_converter.ui import presenters, theme
from ffpfsc_converter.ui.dnd import HAS_DND, create_root, register_drop_target

_PRESETS_BY_LABEL = {p.label: p for p in PRESETS}
_ESTIMATE_LEVELS = sorted({p.level for p in PRESETS})
_DROP_HINT_DND = (
    "Arrastra aquí la(s) carpeta(s) del juego\n"
    "(o un archivo .exfat / .ffpkg) — o haz clic para elegir"
)
_DROP_HINT_CLICK = "Haz clic para seleccionar la carpeta del juego"
_DEFAULT_OUTPUT_TEXT = "Misma carpeta que el juego"
_COLUMNS = (
    # (id, encabezado, ancho, alineación)
    ("titulo", "Nombre del juego", 340, "w"),
    ("juego", "Carpeta / archivo", 160, "w"),
    ("tamano", "Tamaño", 90, "e"),
    ("estimado", "Peso final estimado", 170, "e"),
    ("estado", "Estado", 220, "w"),
)


class MainWindow:
    def __init__(self, initial_paths: Iterable[Path] = ()) -> None:
        self.root = create_root()
        self.root.title(APP_TITLE)
        self.root.geometry(theme.WINDOW_SIZE)
        self.root.minsize(*theme.WINDOW_MIN_SIZE)

        self._jobs: list[ConversionJob] = []
        self._events: queue.Queue[Event] = queue.Queue()
        self._runner = ConversionRunner(self._events.put)
        self._output_dir: Path | None = None  # None = junto a cada juego

        self._cpu_total = os.cpu_count() or 2
        self._cores_var = tk.IntVar(value=self._cpu_total)
        self._preset_var = tk.StringVar(value=DEFAULT_PRESET.label)
        self._verify_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._handlers: dict[type, Callable] = {
            JobInfoReady: self._on_job_info,
            JobSizeReady: self._on_job_size,
            JobEstimateReady: self._on_job_estimate,
            JobStarted: self._on_job_started,
            JobProgress: self._on_job_progress,
            LogMessage: self._on_log_message,
            JobFinished: self._on_job_finished,
            QueueFinished: self._on_queue_finished,
        }
        self.root.after(theme.EVENT_POLL_MS, self._poll_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.add_paths(initial_paths)

    def run(self) -> None:
        self.root.mainloop()

    # ================================================================ UI
    def _build_ui(self) -> None:
        style = ttk.Style()
        with contextlib.suppress(tk.TclError):
            style.theme_use(theme.TTK_THEME)
        self._build_drop_zone()
        self._build_options()
        self._build_job_table()
        self._build_progress()
        self._build_buttons()
        self._build_log()

    def _build_drop_zone(self) -> None:
        self._drop = tk.Label(
            self.root,
            text=_DROP_HINT_DND if HAS_DND else _DROP_HINT_CLICK,
            relief="ridge", bd=2, height=5, cursor="hand2",
            font=theme.DROP_ZONE_FONT, bg=theme.DROP_ZONE_BG, fg=theme.DROP_ZONE_FG,
        )
        self._drop.pack(fill="x", **theme.PADDING)
        self._drop.bind("<Button-1>", lambda _e: self.pick_folder())
        register_drop_target(self._drop, self.add_paths)
        register_drop_target(self.root, self.add_paths)

    def _build_options(self) -> None:
        opts = ttk.Frame(self.root)
        opts.pack(fill="x", **theme.PADDING)

        ttk.Label(opts, text="Modo:").grid(row=0, column=0, sticky="w")
        combo = ttk.Combobox(opts, textvariable=self._preset_var, values=list(_PRESETS_BY_LABEL),
                             state="readonly", width=34)
        combo.grid(row=0, column=1, sticky="w", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_estimates())
        ttk.Label(opts, text="Núcleos CPU:").grid(row=0, column=2, sticky="e", padx=(16, 0))
        ttk.Spinbox(opts, from_=1, to=self._cpu_total, textvariable=self._cores_var,
                    width=5).grid(row=0, column=3, sticky="w", padx=6)
        ttk.Label(opts, text=f"(detectados: {self._cpu_total})").grid(row=0, column=4, sticky="w")

        ttk.Label(opts, text="Guardar en:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._outdir_label = ttk.Label(opts, text=_DEFAULT_OUTPUT_TEXT, width=48)
        self._outdir_label.grid(row=1, column=1, columnspan=2, sticky="w", padx=6, pady=(6, 0))
        ttk.Button(opts, text="Cambiar…", command=self.pick_output_dir).grid(
            row=1, column=3, sticky="w", padx=6, pady=(6, 0))
        ttk.Checkbutton(opts, text="Verificación completa al final (más lento)",
                        variable=self._verify_var).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))

    def _build_job_table(self) -> None:
        self._tree = ttk.Treeview(self.root, columns=[c[0] for c in _COLUMNS],
                                  show="headings", height=6)
        for col_id, heading, width, anchor in _COLUMNS:
            self._tree.heading(col_id, text=heading)
            self._tree.column(col_id, width=width, anchor=anchor)
        self._tree.pack(fill="both", expand=True, **theme.PADDING)

    def _build_progress(self) -> None:
        frame = ttk.Frame(self.root)
        frame.pack(fill="x", **theme.PADDING)
        self._pbar = ttk.Progressbar(frame, maximum=100)
        self._pbar.pack(fill="x")
        self._status = ttk.Label(frame, text="Listo.")
        self._status.pack(anchor="w", pady=(4, 0))

    def _build_buttons(self) -> None:
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", **theme.PADDING)
        self._start_btn = ttk.Button(bar, text="▶ Convertir", command=self.start)
        self._start_btn.pack(side="left")
        self._cancel_btn = ttk.Button(bar, text="■ Cancelar", command=self.cancel,
                                      state="disabled")
        self._cancel_btn.pack(side="left", padx=6)
        ttk.Button(bar, text="+ Archivo .exfat…", command=self.pick_file).pack(
            side="left", padx=6)
        ttk.Button(bar, text="Quitar seleccionado", command=self.remove_selected).pack(
            side="left", padx=6)
        ttk.Button(bar, text="Abrir carpeta de salida", command=self.open_output).pack(
            side="right")

    def _build_log(self) -> None:
        self._log = tk.Text(self.root, height=7, font=theme.LOG_FONT,
                            bg=theme.LOG_BG, fg=theme.LOG_FG, state="disabled")
        self._log.pack(fill="both", **theme.PADDING)

    # =========================================================== acciones
    def pick_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona la carpeta del juego",
                                         initialdir=_initial_dir())
        if folder:
            self.add_path(Path(folder))

    def pick_file(self) -> None:
        file = filedialog.askopenfilename(
            title="Selecciona la imagen del juego",
            initialdir=_initial_dir(),
            filetypes=[("Imágenes de juego", "*.exfat *.ffpkg"), ("Todos", "*")])
        if file:
            self.add_path(Path(file))

    def pick_output_dir(self) -> None:
        folder = filedialog.askdirectory(title="Carpeta donde guardar los .ffpfsc")
        if not folder:
            return
        self._output_dir = Path(folder)
        self._outdir_label.configure(text=folder)
        for job in self._queued_jobs():
            job.output = output_path_for(job.source, self._output_dir)

    def add_paths(self, paths: Iterable[Path]) -> None:
        for path in paths:
            self.add_path(path)

    def add_path(self, path: Path) -> None:
        if self._runner.is_running:
            messagebox.showinfo(APP_TITLE, "Espera a que termine la conversión actual.")
            return
        try:
            job = create_job(path, self._output_dir)
        except ConverterError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        if any(j.game_root == job.game_root for j in self._queued_jobs()):
            return
        self._jobs.append(job)
        self._tree.insert("", "end", iid=job.id, values=(
            "leyendo…", presenters.source_display_name(job), "calculando…",
            presenters.PENDING_TEXT, presenters.QUEUED_TEXT))
        if job.game_root != path:
            self._write_log(f"Juego detectado en: {job.game_root}")
        start_analysis(job, _ESTIMATE_LEVELS, self._events.put)

    def remove_selected(self) -> None:
        if self._runner.is_running:
            return
        selected = set(self._tree.selection())
        self._jobs = [j for j in self._jobs if j.id not in selected]
        for iid in selected:
            self._tree.delete(iid)

    def open_output(self) -> None:
        target = self._output_dir or (self._jobs[-1].output.parent if self._jobs else None)
        if target:
            open_in_file_manager(target)

    def start(self) -> None:
        pending = self._queued_jobs()
        if not pending:
            messagebox.showinfo(APP_TITLE, "Agrega primero una carpeta de juego.")
            return
        level = self._selected_preset().level
        if not all(self._confirm_job(job, level) for job in pending):
            return
        options = ConversionOptions(
            compression_level=level,
            cpu_count=max(1, int(self._cores_var.get())),
            full_verify=self._verify_var.get(),
        )
        self._set_running(True)
        self._runner.start(pending, options)

    def cancel(self) -> None:
        self._runner.cancel()
        self._status.configure(text="Cancelando…")

    def _on_close(self) -> None:
        if self._runner.is_running and not messagebox.askyesno(
                APP_TITLE, "Hay una conversión en curso. ¿Cancelarla y salir?"):
            return
        self._runner.cancel()
        self.root.destroy()

    # ============================================================ eventos
    def _poll_events(self) -> None:
        try:
            while True:
                event = self._events.get_nowait()
                self._handlers[type(event)](event)
        except queue.Empty:
            pass
        self.root.after(theme.EVENT_POLL_MS, self._poll_events)

    def _on_job_info(self, event: JobInfoReady) -> None:
        self._set_cell(event.job, "titulo", presenters.game_info_text(event.job.info))

    def _on_job_size(self, event: JobSizeReady) -> None:
        self._set_cell(event.job, "tamano", presenters.format_size(event.job.size))

    def _on_job_estimate(self, event: JobEstimateReady) -> None:
        job = event.job
        level = self._selected_preset().level
        self._set_cell(job, "estimado", presenters.estimate_text(job, level))
        self._write_log(presenters.estimates_summary(job, PRESETS))

    def _on_job_started(self, event: JobStarted) -> None:
        name = event.job.source.name
        self._set_cell(event.job, "estado", presenters.RUNNING_TEXT)
        self._pbar["value"] = 0
        self._write_log(f"\n=== {name} ===\n$ {event.command}")
        self._status.configure(text=f"Convirtiendo {name}…")

    def _on_job_progress(self, event: JobProgress) -> None:
        text = presenters.progress_text(event.progress)
        self._pbar["value"] = event.progress.percent
        self._set_cell(event.job, "estado", text)
        self._status.configure(text=f"{event.job.source.name}: {text}")

    def _on_log_message(self, event: LogMessage) -> None:
        self._write_log(event.text)

    def _on_job_finished(self, event: JobFinished) -> None:
        self._set_cell(event.job, "estado", presenters.result_text(event.job, event.result))
        if event.result.succeeded:
            self._pbar["value"] = 100

    def _on_queue_finished(self, event: QueueFinished) -> None:
        self._set_running(False)
        self._status.configure(text="Cancelado." if event.cancelled else "Terminado.")

    # ========================================================== helpers
    def _queued_jobs(self) -> list[ConversionJob]:
        return [j for j in self._jobs if j.is_queued]

    def _selected_preset(self) -> CompressionPreset:
        return _PRESETS_BY_LABEL[self._preset_var.get()]

    def _confirm_job(self, job: ConversionJob, level: int) -> bool:
        """Pide confirmación si se va a sobrescribir o puede faltar espacio."""
        if job.output.exists() and not messagebox.askyesno(
                APP_TITLE, f"Ya existe:\n{job.output}\n\n¿Sobrescribir?"):
            return False
        space = check_free_space(job, level)
        if space is None or space.is_enough:
            return True
        return messagebox.askyesno(
            APP_TITLE,
            f"Espacio libre en destino: {presenters.format_size(space.free)}\n"
            f"Peso final estimado (+{(FREE_SPACE_MARGIN - 1) * 100:.0f}% margen): "
            f"{presenters.format_size(space.needed)}\n\n"
            "Probablemente NO alcanza. ¿Continuar igual?")

    def _set_running(self, running: bool) -> None:
        self._start_btn.configure(state="disabled" if running else "normal")
        self._cancel_btn.configure(state="normal" if running else "disabled")

    def _set_cell(self, job: ConversionJob, column: str, value: str) -> None:
        if self._tree.exists(job.id):
            self._tree.set(job.id, column, value)

    def _refresh_estimates(self) -> None:
        level = self._selected_preset().level
        for job in self._jobs:
            self._set_cell(job, "estimado", presenters.estimate_text(job, level))

    def _write_log(self, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text.rstrip() + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")


def _initial_dir() -> str:
    desktop = Path.home() / "Escritorio"
    return str(desktop if desktop.exists() else Path.home())
