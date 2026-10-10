"""Lista de juegos de la pestaña Convertir: una fila por juego.

Cada fila muestra la ficha con iniciales, nombre y datos del juego, tamaño y
estimación, una píldora de estado con barra de progreso y, cuando corresponde,
el botón «Subir a la PS5». Clic selecciona la fila; Ctrl+clic suma a la selección.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable
from tkinter import ttk

from ffpfsc_converter.ui.job_presenters import SizeText
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import Tile, icon_button
from ffpfsc_converter.ui.widgets.scroll_frame import ScrollFrame

_EMPTY_TEXT = ("Todavía no hay juegos en la cola.\n"
               "Arrastra una carpeta de juego o una imagen .exfat / .ffpkg a la zona de arriba.")
#: Estado de la fila → sufijo del estilo de píldora.
_PILL = {"wait": "Wait", "run": "Run", "ok": "Ok", "warn": "Warn", "bad": "Bad"}
_BAR = {"run": "Thin", "ok": "OkThin", "warn": "WarnThin"}
#: Ancho reservado para el botón «Subir a la PS5» (píxeles lógicos).
_ACTION_WIDTH = 140


class _Row(ttk.Frame):
    """Fila de un juego."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, on_action: Callable[[], None],
                 on_click: Callable[[tk.Event], None]) -> None:
        """Crea los widgets de la fila.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            on_action (Callable[[], None]): Acción del botón «Subir a la PS5».
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
        self.pill.configure(style=f"{surface}.Pill{_PILL.get(self.kind, 'Wait')}.TLabel")
        self.action.configure(style=f"{surface}.SmallAccent.TButton")
        self.tile.show(self.tile_title, "accent_soft" if selected else "surface")

    @property
    def tile_title(self) -> str:
        """Obtiene el nombre que muestra la fila (para las iniciales de la ficha).

        Returns:
            str: Nombre del juego.
        """
        return str(self.title.cget("text"))


class JobList(ttk.Frame):
    """Filas de los juegos en cola."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager,
                 on_action: Callable[[str], None]) -> None:
        """Crea la lista vacía.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            on_action (Callable[[str], None]): Recibe el id de la fila cuyo botón
                «Subir a la PS5» se pulsó.
        """
        super().__init__(parent, style="Card.TFrame", padding=theme.metrics.px(4))
        self._theme, self._on_action = theme, on_action
        self._scroll = ScrollFrame(self, theme)
        self._scroll.pack(fill="both", expand=True)
        self._rows: dict[str, _Row] = {}
        self._separators: dict[str, ttk.Separator] = {}
        self._selected: set[str] = set()
        self._empty = ttk.Label(self._scroll.inner, text=_EMPTY_TEXT, style="CardMuted.TLabel",
                                justify="center", padding=theme.metrics.px(28))
        self._empty.pack(fill="x")

    def add_row(self, row_id: str, title: str, meta: str) -> None:
        """Agrega un juego al final.

        Args:
            row_id (str): Identificador de la fila (id del trabajo).
            title (str): Nombre provisional.
            meta (str): Texto secundario (carpeta o imagen).
        """
        self._empty.pack_forget()
        if self._rows:
            separator = ttk.Separator(self._scroll.inner)
            separator.pack(fill="x")
            self._separators[row_id] = separator
        row = _Row(self._scroll.inner, self._theme, lambda: self._on_action(row_id),
                   lambda event: self._on_click(row_id, event))
        row.pack(fill="x")
        self._rows[row_id] = row
        self.set_info(row_id, title, meta)
        self.set_status(row_id, "wait", "En cola")

    def set_info(self, row_id: str, title: str, meta: str) -> None:
        """Muestra el nombre y los datos del juego.

        Args:
            row_id (str): Identificador de la fila.
            title (str): Nombre del juego.
            meta (str): Title ID y versión, o el origen.
        """
        if row := self._rows.get(row_id):
            row.title.configure(text=title)
            row.meta.configure(text=meta)
            row.tile.show(title)

    def set_sizes(self, row_id: str, sizes: SizeText) -> None:
        """Muestra el tamaño, la estimación (en verde) y el ahorro.

        Args:
            row_id (str): Identificador de la fila.
            sizes (SizeText): Textos de tamaño de la fila.
        """
        if row := self._rows.get(row_id):
            row.size.configure(text=sizes.original)
            row.estimate.configure(text=sizes.estimate)
            row.size_note.configure(text=sizes.note)

    def set_status(self, row_id: str, kind: str, label: str, detail: str = "",
                   percent: float | None = None) -> None:
        """Muestra el estado con su píldora, detalle y barra opcional.

        Args:
            row_id (str): Identificador de la fila.
            kind (str): ``"wait"``, ``"run"``, ``"ok"``, ``"warn"`` o ``"bad"``.
            label (str): Texto de la píldora.
            detail (str): Texto bajo la píldora (velocidad, tiempo restante, motivo).
            percent (float | None): Avance para la barra; ``None`` la oculta.
        """
        row = self._rows.get(row_id)
        if row is None:
            return
        row.kind = kind
        row.pill.configure(text=label, style=f"{row.surface}.Pill{_PILL.get(kind, 'Wait')}.TLabel")
        row.detail.configure(text=detail)
        if percent is None:
            row.bar.grid_remove()
            row.detail.grid(row=1, column=3, sticky="nw")
            return
        row.bar.configure(value=percent, style=f"{_BAR.get(kind, 'Thin')}.Horizontal.TProgressbar")
        row.bar.grid(row=1, column=3, sticky="new", pady=(self._theme.metrics.px(6), 0))
        row.detail.grid(row=2, column=3, sticky="nw")

    def set_action(self, row_id: str, visible: bool) -> None:
        """Muestra u oculta el botón «Subir a la PS5» de la fila.

        Args:
            row_id (str): Identificador de la fila.
            visible (bool): ``True`` para mostrarlo.
        """
        if row := self._rows.get(row_id):
            if visible:
                row.action.grid()
            else:
                row.action.grid_remove()

    def selected_ids(self) -> set[str]:
        """Obtiene las filas seleccionadas.

        Returns:
            set[str]: Identificadores seleccionados.
        """
        return set(self._selected)

    def delete_rows(self, row_ids: Iterable[str]) -> None:
        """Quita filas de la lista.

        Args:
            row_ids (Iterable[str]): Identificadores a quitar.
        """
        for row_id in list(row_ids):
            if row := self._rows.pop(row_id, None):
                row.destroy()
            if separator := self._separators.pop(row_id, None):
                separator.destroy()
            self._selected.discard(row_id)
        if self._rows:
            first = next(iter(self._rows))
            if separator := self._separators.pop(first, None):
                separator.destroy()
        else:
            self._empty.pack(fill="x")

    def _on_click(self, row_id: str, event: tk.Event) -> None:
        """Selecciona la fila (Ctrl suma o quita de la selección).

        Args:
            row_id (str): Fila pulsada.
            event (tk.Event): Evento del clic (para leer Ctrl).
        """
        additive = bool(event.state & 0x0004)
        if not additive:
            self._selected = set() if row_id in self._selected else {row_id}
        elif row_id in self._selected:
            self._selected.discard(row_id)
        else:
            self._selected.add(row_id)
        for key, row in self._rows.items():
            row.set_selected(key in self._selected)
