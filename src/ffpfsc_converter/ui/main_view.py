"""Vista Convertir: construye los widgets y expone métodos para actualizarlos.

La vista no conoce los servicios: avisa de las acciones del usuario mediante
los callbacks de :class:`ViewCallbacks` y el controlador decide qué hacer.
"""
from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.infrastructure.app_log import LOGGER_NAME
from ffpfsc_converter.ui.dnd import HAS_DND
from ffpfsc_converter.ui.job_list import JobList
from ffpfsc_converter.ui.options_panel import OptionsPanel
from ffpfsc_converter.ui.theme import Palette, ThemeManager
from ffpfsc_converter.ui.widgets.basics import icon_button
from ffpfsc_converter.ui.widgets.drop_zone import DropZone

_DROP_TITLE = ("Arrastra juegos: carpetas o imágenes .exfat / .ffpkg" if HAS_DND
               else "Elige un juego: carpeta o imagen .exfat / .ffpkg")
_DROP_HINT = "Busca el eboot.bin en subcarpetas · un .ffpfsc queda listo para subir"


@dataclass(frozen=True)
class ViewCallbacks:
    """Acciones del usuario que la vista notifica al controlador.

    Attributes:
        on_paths (Callable[[list[Path]], None]): Se soltaron rutas en la ventana.
        on_pick_folder (Callable[[], None]): Botón "Elegir carpeta" o clic en la zona.
        on_pick_file (Callable[[], None]): Botón "Elegir imagen".
        on_output_changed (Callable[[Path | None], None]): Se eligió otra carpeta de destino
            (``None`` = junto a cada juego).
        on_preset_changed (Callable[[], None]): Cambió el modo de compresión.
        on_start (Callable[[], None]): Botón "Convertir".
        on_cancel (Callable[[], None]): Botón "Cancelar".
        on_remove (Callable[[], None]): Botón "Quitar seleccionados".
        on_open_output (Callable[[], None]): Botón "Abrir carpeta de salida".
        on_upload_all (Callable[[], None]): Botón "Subir completados a la PS5".
        on_upload_row (Callable[[str], None]): Botón "Subir a la PS5" de una fila.
    """

    on_paths: Callable[[list[Path]], None]
    on_pick_folder: Callable[[], None]
    on_pick_file: Callable[[], None]
    on_output_changed: Callable[[Path | None], None]
    on_preset_changed: Callable[[], None]
    on_start: Callable[[], None]
    on_cancel: Callable[[], None]
    on_remove: Callable[[], None]
    on_open_output: Callable[[], None]
    on_upload_all: Callable[[], None]
    on_upload_row: Callable[[str], None]


class MainView:
    """Widgets de la vista Convertir.

    Attributes:
        options (OptionsPanel): Tarjeta con las opciones de conversión.
        table (JobList): Filas de los juegos de la cola.
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager, callbacks: ViewCallbacks) -> None:
        """Construye la vista dentro de su contenedor.

        Args:
            parent (tk.Misc): Contenedor de la vista.
            theme (ThemeManager): Tema.
            callbacks (ViewCallbacks): Acciones a notificar al controlador.
        """
        self._theme = theme
        m = theme.metrics
        self._root = ttk.Frame(parent, style="TFrame", padding=(m.px(26), m.px(22)))
        self._root.pack(fill="both", expand=True)
        self._build_header(callbacks)
        DropZone(self._root, theme, _DROP_TITLE, _DROP_HINT,
                 (("Elegir carpeta…", callbacks.on_pick_folder),
                  ("Elegir imagen…", callbacks.on_pick_file)),
                 callbacks.on_paths).pack(fill="x", pady=(m.px(16), 0))
        self.options = OptionsPanel(self._root, theme, callbacks.on_preset_changed,
                                    callbacks.on_output_changed)
        self.options.pack(fill="x", pady=(m.px(14), 0))
        head = ttk.Frame(self._root, style="TFrame")
        head.pack(fill="x", pady=(m.px(18), m.px(8)))
        ttk.Label(head, text="Cola", style="Heading.TLabel").pack(side="left")
        self._summary = ttk.Label(head, style="Muted.TLabel")
        self._summary.pack(side="left", padx=(m.px(12), 0))
        icon_button(head, theme, "Quitar seleccionados", "x", callbacks.on_remove,
                    style="Ghost.TButton", role="muted").pack(side="right")
        self._build_footer(callbacks)
        self._build_log()
        self.table = JobList(self._root, theme, callbacks.on_upload_row)
        self.table.pack(fill="both", expand=True)

    def _build_header(self, callbacks: ViewCallbacks) -> None:
        """Crea el título de la vista y el acceso a la carpeta de salida.

        Args:
            callbacks (ViewCallbacks): Acciones a notificar al controlador.
        """
        head = ttk.Frame(self._root, style="TFrame")
        head.pack(fill="x")
        texts = ttk.Frame(head, style="TFrame")
        texts.pack(side="left")
        ttk.Label(texts, text="Convertir", style="Title.TLabel").pack(anchor="w")
        ttk.Label(texts, text="Comprime juegos a .ffpfsc para ShadowMount+",
                  style="Muted.TLabel").pack(anchor="w")
        icon_button(head, self._theme, "Abrir carpeta de salida", "folder",
                    callbacks.on_open_output, style="Ghost.TButton", role="muted").pack(
            side="right", anchor="s")

    def _build_footer(self, callbacks: ViewCallbacks) -> None:
        """Crea el pie: registro plegable, estado y botones de acción.

        Args:
            callbacks (ViewCallbacks): Acciones a notificar al controlador.
        """
        m, theme = self._theme.metrics, self._theme
        bar = ttk.Frame(self._root, style="TFrame")
        bar.pack(side="bottom", fill="x", pady=(m.px(12), 0))
        # Los botones se empaquetan primero para que, si falta ancho, se recorte el estado.
        self._start_btn = icon_button(bar, theme, "Convertir", "play", callbacks.on_start,
                                      style="Accent.TButton", role="accent_ink")
        self._start_btn.pack(side="right")
        self._upload_btn = icon_button(bar, theme, "Subir completados a la PS5", "upload",
                                       callbacks.on_upload_all)
        self._upload_btn.pack(side="right", padx=(0, m.px(8)))
        self._upload_btn.state(["disabled"])
        self._cancel_btn = icon_button(bar, theme, "Cancelar", "stop", callbacks.on_cancel,
                                       style="Danger.TButton", role="bad")
        self._cancel_btn.pack(side="right", padx=(0, m.px(8)))
        self._cancel_btn.state(["disabled"])
        self._log_toggle = icon_button(bar, theme, "Registro técnico", "chevron_right",
                                       self._toggle_log, style="Ghost.TButton", role="muted")
        self._log_toggle.pack(side="left")
        self._status = ttk.Label(bar, text="Listo.", style="Muted.TLabel")
        self._status.pack(side="left", padx=(m.px(8), 0))

    def _build_log(self) -> None:
        """Crea el registro técnico de MkPFS (oculto hasta que se despliega)."""
        p = self._theme.palette
        self._log = tk.Text(self._root, height=8, font=self._theme.fonts.mono, relief="flat",
                            bd=0, padx=self._theme.metrics.px(10), pady=self._theme.metrics.px(8),
                            background=p.log_bg, foreground=p.log_fg, state="disabled",
                            highlightthickness=1, highlightbackground=p.line)
        self._log_visible = False
        self._theme.on_change(self._paint_log)

    def _paint_log(self, p: Palette) -> None:
        """Aplica los colores del tema al registro.

        Args:
            p (Palette): Paleta actual.
        """
        self._log.configure(background=p.log_bg, foreground=p.log_fg, highlightbackground=p.line)

    def _toggle_log(self) -> None:
        """Muestra u oculta el registro técnico."""
        self._log_visible = not self._log_visible
        icon = "chevron_down" if self._log_visible else "chevron_right"
        self._log_toggle.configure(image=self._theme.icons.get(icon, 16, "muted"))
        if self._log_visible:
            self._log.pack(side="bottom", fill="x", pady=(self._theme.metrics.px(10), 0),
                           before=self.table)
        else:
            self._log.pack_forget()

    def write_log(self, text: str) -> None:
        """Agrega una línea al registro técnico (y al archivo de registro) y baja al final.

        Args:
            text (str): Texto a agregar (se recortan los saltos finales).
        """
        logging.getLogger(LOGGER_NAME).info(text.rstrip())
        self._log.configure(state="normal")
        self._log.insert("end", text.rstrip() + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def set_status(self, text: str) -> None:
        """Cambia el texto de estado del pie.

        Args:
            text (str): Texto a mostrar.
        """
        self._status.configure(text=text)

    def set_summary(self, text: str) -> None:
        """Muestra el resumen de la cola (cantidad y tamaños).

        Args:
            text (str): Resumen ya formateado.
        """
        self._summary.configure(text=text)

    def set_upload_enabled(self, enabled: bool) -> None:
        """Habilita "Subir completados a la PS5" si hay juegos listos sin subir.

        Args:
            enabled (bool): ``True`` para habilitar el botón.
        """
        self._upload_btn.state(["!disabled"] if enabled else ["disabled"])

    def set_running(self, running: bool) -> None:
        """Habilita o deshabilita los botones según haya una conversión en curso.

        Args:
            running (bool): ``True`` mientras se convierte la cola.
        """
        self._start_btn.state(["disabled"] if running else ["!disabled"])
        self._cancel_btn.state(["!disabled"] if running else ["disabled"])
