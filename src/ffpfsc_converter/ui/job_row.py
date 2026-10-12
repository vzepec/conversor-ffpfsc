"""Fila de un juego de la vista Convertir: ficha, datos, tamaños, estado y botón."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.ui.presenters import SKIP_VERIFY_TEXT
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import Tile, icon_button

#: Estado de la fila → sufijo del estilo de píldora.
PILL_STYLES = {"wait": "Wait", "run": "Run", "ok": "Ok", "warn": "Warn", "bad": "Bad"}
#: Ancho reservado para el botón de la fila (píxeles lógicos).
_ACTION_WIDTH = 170
#: Botones posibles de la fila: modo → (texto, icono).
_BUTTONS = {"upload": ("Subir a la PS5", "upload"),
            "skip": (SKIP_VERIFY_TEXT, "chevron_right")}


class JobRow(ttk.Frame):
    """Fila de un juego.

    Attributes:
        mode (str | None): Botón visible: ``"upload"``, ``"skip"`` o ``None``.
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager, on_action: Callable[[], None],
                 on_click: Callable[[tk.Event], None]) -> None:
        """Crea los widgets de la fila.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            on_action (Callable[[], None]): Acción del botón (según ``mode``).
            on_click (Callable[[tk.Event], None]): Clic sobre la fila (selección).
        """
        m = theme.metrics
        super().__init__(parent, style="Surface.TFrame", padding=(m.px(14), m.px(12)))
        for column, weight in ((1, 6), (2, 4), (3, 5)):
            self.columnconfigure(column, weight=weight, uniform="row")
        # Se reserva el ancho del botón en todas las filas para que las columnas queden alineadas.
        self.columnconfigure(4, minsize=m.px(_ACTION_WIDTH))
        self.kind, self.surface = "wait", "Card"
        self.tile = Tile(self, theme)
        self.tile.grid(row=0, column=0, rowspan=2, padx=(0, m.px(14)))
        self.title, self.meta = ttk.Label(self), ttk.Label(self)
        self.sizes = ttk.Frame(self)
        self.size, self.estimate = ttk.Label(self.sizes), ttk.Label(self.sizes)
        self.size.pack(side="left")
        self.estimate.pack(side="left", padx=(m.px(4), 0))
        self.size_note, self.pill, self.detail = ttk.Label(self), ttk.Label(self), ttk.Label(self)
        self.bar = ttk.Progressbar(self, maximum=100, style="Thin.Horizontal.TProgressbar")
        self.action = icon_button(self, theme, "Subir a la PS5", "upload", on_action,
                                  style="Card.SmallAccent.TButton", role="accent_ink")
        self.title.grid(row=0, column=1, sticky="sw")
        self.meta.grid(row=1, column=1, sticky="nw")
        self.sizes.grid(row=0, column=2, sticky="sw", padx=m.px(10))
        self.size_note.grid(row=1, column=2, sticky="nw", padx=m.px(10))
        self.pill.grid(row=0, column=3, sticky="sw")
        self.detail.grid(row=1, column=3, sticky="nw")
        self.action.grid(row=0, column=4, rowspan=2, sticky="e", padx=(m.px(10), 0))
        self.action.grid_remove()
        self.mode: str | None = None
        self._images = {mode: (theme.icons.get(icon, 14, "accent_ink"), "disabled",
                               theme.icons.get(icon, 14, "muted"))
                        for mode, (_text, icon) in _BUTTONS.items()}
        for widget in (self, self.title, self.meta, self.sizes, self.size, self.estimate,
                       self.size_note, self.pill, self.detail, self.tile):
            widget.bind("<Button-1>", on_click)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        """Resalta o no la fila.

        Args:
            selected (bool): ``True`` si está seleccionada.
        """
        surface = self.surface = "Sel" if selected else "Card"
        self.configure(style="Sel.TFrame" if selected else "Surface.TFrame")
        self.sizes.configure(style="Sel.TFrame" if selected else "Surface.TFrame")
        for widget, role in ((self.title, "Bold"), (self.meta, "MonoMuted"), (self.size, ""),
                             (self.estimate, "Ok"), (self.size_note, "Small"),
                             (self.detail, "Small")):
            widget.configure(style=f"{surface}{role}.TLabel")
        self.pill.configure(style=f"{surface}.Pill{PILL_STYLES.get(self.kind, 'Wait')}.TLabel")
        self.action.configure(style=f"{surface}.SmallAccent.TButton")
        self.tile.show(self.tile_title, "accent_soft" if selected else "surface")

    def set_button(self, mode: str | None) -> None:
        """Muestra el botón de la fila o lo oculta.

        Args:
            mode (str | None): ``"upload"`` («Subir a la PS5»), ``"skip"`` («Saltar
                verificación») o ``None`` para ocultarlo.
        """
        self.mode = mode
        if mode is None:
            self.action.grid_remove()
            return
        self.action.configure(text=f" {_BUTTONS[mode][0]}", image=self._images[mode])
        self.action.grid()

    @property
    def tile_title(self) -> str:
        """Obtiene el nombre que muestra la fila (para las iniciales de la ficha).

        Returns:
            str: Nombre del juego.
        """
        return str(self.title.cget("text"))
