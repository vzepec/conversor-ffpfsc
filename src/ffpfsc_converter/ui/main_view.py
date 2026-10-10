"""Vista principal: construye los widgets y expone métodos para actualizarlos.

La vista no conoce los servicios: avisa de las acciones del usuario mediante
los callbacks de :class:`ViewCallbacks` y el controlador decide qué hacer.
"""
from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.ui import theme
from ffpfsc_converter.ui.dnd import HAS_DND, register_drop_target
from ffpfsc_converter.ui.job_table import JobTable
from ffpfsc_converter.ui.options_panel import OptionsPanel

_DROP_HINT_DND = (
    "Arrastra aquí la(s) carpeta(s) del juego\n"
    "(o un archivo .exfat / .ffpkg) — o haz clic para elegir"
)
_DROP_HINT_CLICK = "Haz clic para seleccionar la carpeta del juego"


@dataclass(frozen=True)
class ViewCallbacks:
    """Acciones del usuario que la vista notifica al controlador.

    Attributes:
        on_paths (Callable[[list[Path]], None]): Se soltaron rutas en la ventana.
        on_pick_folder (Callable[[], None]): Clic en la zona de soltar.
        on_pick_file (Callable[[], None]): Botón "+ Archivo .exfat…".
        on_pick_output_dir (Callable[[], None]): Botón "Cambiar…".
        on_preset_changed (Callable[[], None]): Cambió el modo de compresión.
        on_start (Callable[[], None]): Botón "Convertir".
        on_cancel (Callable[[], None]): Botón "Cancelar".
        on_remove (Callable[[], None]): Botón "Quitar seleccionado".
        on_open_output (Callable[[], None]): Botón "Abrir carpeta de salida".
    """

    on_paths: Callable[[list[Path]], None]
    on_pick_folder: Callable[[], None]
    on_pick_file: Callable[[], None]
    on_pick_output_dir: Callable[[], None]
    on_preset_changed: Callable[[], None]
    on_start: Callable[[], None]
    on_cancel: Callable[[], None]
    on_remove: Callable[[], None]
    on_open_output: Callable[[], None]


class MainView:
    """Widgets de la ventana principal.

    Attributes:
        options (OptionsPanel): Panel con las opciones de conversión.
        table (JobTable): Tabla con los juegos de la cola.
    """

    def __init__(self, root: tk.Tk, callbacks: ViewCallbacks) -> None:
        """Construye todos los widgets dentro de la ventana raíz.

        Args:
            root (tk.Tk): Ventana raíz.
            callbacks (ViewCallbacks): Acciones a notificar al controlador.
        """
        self._root = root
        with contextlib.suppress(tk.TclError):
            ttk.Style().theme_use(theme.TTK_THEME)
        self._build_drop_zone(callbacks)
        self.options = OptionsPanel(root, callbacks.on_preset_changed,
                                    callbacks.on_pick_output_dir)
        self.options.pack(fill="x", **theme.PADDING)
        self.table = JobTable(root)
        self.table.pack(fill="both", expand=True, **theme.PADDING)
        self._build_progress()
        self._build_buttons(callbacks)
        self._build_log()

    def _build_drop_zone(self, callbacks: ViewCallbacks) -> None:
        """Crea la zona superior donde se sueltan o eligen los juegos.

        Args:
            callbacks (ViewCallbacks): Acciones a notificar al controlador.
        """
        drop = tk.Label(
            self._root, text=_DROP_HINT_DND if HAS_DND else _DROP_HINT_CLICK,
            relief="ridge", bd=2, height=5, cursor="hand2",
            font=theme.DROP_ZONE_FONT, bg=theme.DROP_ZONE_BG, fg=theme.DROP_ZONE_FG,
        )
        drop.pack(fill="x", **theme.PADDING)
        drop.bind("<Button-1>", lambda _e: callbacks.on_pick_folder())
        register_drop_target(drop, callbacks.on_paths)
        register_drop_target(self._root, callbacks.on_paths)

    def _build_progress(self) -> None:
        """Crea la barra de progreso y la línea de estado."""
        frame = ttk.Frame(self._root)
        frame.pack(fill="x", **theme.PADDING)
        self._pbar = ttk.Progressbar(frame, maximum=100)
        self._pbar.pack(fill="x")
        self._status = ttk.Label(frame, text="Listo.")
        self._status.pack(anchor="w", pady=(4, 0))

    def _build_buttons(self, callbacks: ViewCallbacks) -> None:
        """Crea la barra de botones de acción.

        Args:
            callbacks (ViewCallbacks): Acciones a notificar al controlador.
        """
        bar = ttk.Frame(self._root)
        bar.pack(fill="x", **theme.PADDING)
        self._start_btn = ttk.Button(bar, text="▶ Convertir", command=callbacks.on_start)
        self._start_btn.pack(side="left")
        self._cancel_btn = ttk.Button(bar, text="■ Cancelar", command=callbacks.on_cancel,
                                      state="disabled")
        self._cancel_btn.pack(side="left", padx=6)
        ttk.Button(bar, text="+ Archivo .exfat…", command=callbacks.on_pick_file).pack(
            side="left", padx=6)
        ttk.Button(bar, text="Quitar seleccionado", command=callbacks.on_remove).pack(
            side="left", padx=6)
        ttk.Button(bar, text="Abrir carpeta de salida", command=callbacks.on_open_output).pack(
            side="right")

    def _build_log(self) -> None:
        """Crea el recuadro de registro de solo lectura."""
        self._log = tk.Text(self._root, height=7, font=theme.LOG_FONT,
                            bg=theme.LOG_BG, fg=theme.LOG_FG, state="disabled")
        self._log.pack(fill="both", **theme.PADDING)

    def write_log(self, text: str) -> None:
        """Agrega una línea al registro y desplaza la vista al final.

        Args:
            text (str): Texto a agregar (se recortan los saltos finales).
        """
        self._log.configure(state="normal")
        self._log.insert("end", text.rstrip() + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def set_status(self, text: str) -> None:
        """Cambia la línea de estado bajo la barra de progreso.

        Args:
            text (str): Texto a mostrar.
        """
        self._status.configure(text=text)

    def set_progress(self, percent: int) -> None:
        """Cambia el valor de la barra de progreso.

        Args:
            percent (int): Porcentaje entre ``0`` y ``100``.
        """
        self._pbar["value"] = percent

    def set_running(self, running: bool) -> None:
        """Habilita o deshabilita los botones según haya una conversión en curso.

        Args:
            running (bool): ``True`` mientras se convierte la cola.
        """
        self._start_btn.configure(state="disabled" if running else "normal")
        self._cancel_btn.configure(state="normal" if running else "disabled")
