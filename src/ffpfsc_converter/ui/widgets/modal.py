"""Ventana modal con el aspecto de la app: título, subtítulo, contenido y botones."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.config import APP_TITLE
from ffpfsc_converter.ui.theme import ThemeManager


class Modal(tk.Toplevel):
    """Base de los diálogos: centra la ventana sobre la principal y bloquea el resto.

    Attributes:
        body (ttk.Frame): Contenedor donde cada diálogo agrega su contenido.
        buttons (ttk.Frame): Fila inferior para los botones (se ubican a la derecha).
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager, title: str,
                 subtitle: str = "") -> None:
        """Crea la ventana con su encabezado.

        Args:
            parent (tk.Misc): Ventana principal.
            theme (ThemeManager): Tema.
            title (str): Título del diálogo.
            subtitle (str): Línea secundaria (por ejemplo, una ruta); vacía la omite.
        """
        super().__init__(parent, background=theme.palette.surface)
        self.theme = theme
        m = theme.metrics
        self.title(f"{APP_TITLE} — {title}")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        frame = ttk.Frame(self, style="Surface.TFrame", padding=(m.px(24), m.px(22)))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=title, style="CardHeading.TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(frame, text=subtitle, style="CardMonoMuted.TLabel",
                      wraplength=m.px(500)).pack(anchor="w", pady=(m.px(2), 0))
        self.buttons = ttk.Frame(frame, style="Surface.TFrame")
        self.buttons.pack(side="bottom", fill="x", pady=(m.px(18), 0))
        self.body = ttk.Frame(frame, style="Surface.TFrame")
        self.body.pack(fill="both", expand=True, pady=(m.px(16), 0))

    def add_button(self, text: str, command: Callable[[], None],
                   style: str = "Card.TButton") -> ttk.Button:
        """Agrega un botón a la derecha de la fila inferior.

        Los botones se muestran en el orden en que se agregan, de derecha a izquierda.

        Args:
            text (str): Texto del botón.
            command (Callable[[], None]): Acción.
            style (str): Estilo ttk (``"Card.Accent.TButton"`` para la acción principal).

        Returns:
            ttk.Button: Botón creado.
        """
        button = ttk.Button(self.buttons, text=text, command=command, style=style)
        gap = self.theme.metrics.px(8) if self.buttons.winfo_children()[:-1] else 0
        button.pack(side="right", padx=(0, gap))
        return button

    def show_modal(self) -> None:
        """Centra la ventana sobre la principal y bloquea las demás hasta cerrarla."""
        self.center()
        self.grab_set()

    def center(self) -> None:
        """Ubica la ventana centrada sobre la principal."""
        self.update_idletasks()
        owner = self.master.winfo_toplevel()
        x = owner.winfo_rootx() + (owner.winfo_width() - self.winfo_reqwidth()) // 2
        y = owner.winfo_rooty() + (owner.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
