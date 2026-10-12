"""Lista de juegos de la vista Convertir: una fila por juego.

Cada fila muestra la ficha con iniciales, nombre y datos del juego, tamaño y
estimación, una píldora de estado con barra de progreso y, cuando corresponde,
el botón «Subir a la PS5» (o «Saltar verificación» mientras se verifica un LZ4).
Clic selecciona la fila; Ctrl+clic suma a la selección.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable
from tkinter import ttk

from ffpfsc_converter.ui.job_presenters import SizeText
from ffpfsc_converter.ui.job_row import PILL_STYLES, JobRow
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.scroll_frame import ScrollFrame

_EMPTY_TEXT = ("Todavía no hay juegos en la cola.\n"
               "Arrastra una carpeta de juego o una imagen .exfat / .ffpkg a la zona de arriba.")
_BAR = {"run": "Thin", "ok": "OkThin", "warn": "WarnThin"}


class JobList(ttk.Frame):
    """Filas de los juegos en cola."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager,
                 on_action: Callable[[str], None], on_skip: Callable[[str], None]) -> None:
        """Crea la lista vacía.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            on_action (Callable[[str], None]): Recibe el id de la fila cuyo botón
                «Subir a la PS5» se pulsó.
            on_skip (Callable[[str], None]): Recibe el id de la fila cuyo botón «Saltar
                verificación» se pulsó.
        """
        super().__init__(parent, style="Card.TFrame", padding=theme.metrics.px(4))
        self._theme, self._on_action, self._on_skip = theme, on_action, on_skip
        self._scroll = ScrollFrame(self, theme)
        self._scroll.pack(fill="both", expand=True)
        self._rows: dict[str, JobRow] = {}
        self._separators: dict[str, ttk.Separator] = {}
        self._selected: set[str] = set()
        self._empty = ttk.Label(self._scroll.inner, text=_EMPTY_TEXT, style="CardMuted.TLabel",
                                justify="center", anchor="center", padding=theme.metrics.px(28))
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
        row = JobRow(self._scroll.inner, self._theme, lambda: self._on_button(row_id),
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
        pill = PILL_STYLES.get(kind, "Wait")
        row.pill.configure(text=label, style=f"{row.surface}.Pill{pill}.TLabel")
        row.detail.configure(text=detail)
        if percent is None:
            row.bar.grid_remove()
            row.detail.grid(row=1, column=3, sticky="nw")
            return
        row.bar.configure(value=percent, style=f"{_BAR.get(kind, 'Thin')}.Horizontal.TProgressbar")
        row.bar.grid(row=1, column=3, sticky="new", pady=(self._theme.metrics.px(6), 0))
        row.detail.grid(row=2, column=3, sticky="nw")

    def set_action(self, row_id: str, visible: bool) -> None:
        """Muestra u oculta el botón «Subir a la PS5» de la fila (salvo mientras se verifica).

        Args:
            row_id (str): Identificador de la fila.
            visible (bool): ``True`` para mostrarlo.
        """
        if (row := self._rows.get(row_id)) and row.mode != "skip":
            row.set_button("upload" if visible else None)

    def set_skip(self, row_id: str, visible: bool) -> None:
        """Muestra u oculta el botón «Saltar verificación» (solo mientras se verifica un LZ4).

        Args:
            row_id (str): Identificador de la fila.
            visible (bool): ``True`` para mostrarlo.
        """
        row = self._rows.get(row_id)
        if row is None:
            return
        if visible:
            row.set_button("skip")
        elif row.mode == "skip":
            row.set_button(None)

    def _on_button(self, row_id: str) -> None:
        """Reparte el clic del botón de una fila según lo que muestra.

        Args:
            row_id (str): Identificador de la fila.
        """
        row = self._rows.get(row_id)
        if row is not None and row.mode == "skip":
            self._on_skip(row_id)
        else:
            self._on_action(row_id)

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
