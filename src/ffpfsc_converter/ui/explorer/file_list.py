"""Lista de archivos y carpetas de la PS5 dibujada en un lienzo.

Cada fila muestra icono, nombre (recortado con «…» si no cabe), etiqueta de
tipo, tamaño y fecha. Clic selecciona, Ctrl+clic suma, Mayús+clic selecciona
un rango y doble clic (o Intro) abre la carpeta.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable
from tkinter import ttk

from PIL import ImageTk

from ffpfsc_converter.domain.remote import RemoteEntry
from ffpfsc_converter.ui.explorer import presenters
from ffpfsc_converter.ui.explorer.view_presenters import entry_badge
from ffpfsc_converter.ui.theme import Palette, ThemeManager
from ffpfsc_converter.ui.theme.shapes import render_rounded
from ffpfsc_converter.ui.widgets.scroll_frame import autohide
from ffpfsc_converter.ui.widgets.text_fit import elide

_ROW, _PAD, _SIZE_W, _DATE_W, _ICON_W = 36, 14, 110, 140, 28
_CTRL, _SHIFT = 0x0004, 0x0001
_BADGE_COLORS = {"wait": ("surface2", "muted"), "ok": ("ok_soft", "ok"),
                 "warn": ("warn_soft", "warn")}


class FileList(ttk.Frame):
    """Contenido de una carpeta de la PS5 con selección múltiple."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager,
                 on_open: Callable[[RemoteEntry], None], on_select: Callable[[], None]) -> None:
        """Crea la tarjeta con su encabezado y el lienzo de filas.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            on_open (Callable[[RemoteEntry], None]): Abre un elemento (doble clic o Intro).
            on_select (Callable[[], None]): Avisa que cambió la selección.
        """
        m = self._m = theme.metrics
        super().__init__(parent, style="Card.TFrame", padding=m.px(4))
        self._theme, self._on_open, self._on_select = theme, on_open, on_select
        self._entries: list[RemoteEntry] = []
        self._selected: set[int] = set()
        self._badges: dict[tuple[int, int, str], ImageTk.PhotoImage] = {}
        self._anchor = self._focus = 0
        self._empty = "Conecta la PS5 para ver sus archivos."
        self._build_header()
        body = ttk.Frame(self, style="Surface.TFrame")
        body.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(body, highlightthickness=0, bd=0, takefocus=True,
                                 yscrollincrement=m.px(_ROW))
        bar = ttk.Scrollbar(body, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=autohide(bar))
        self._canvas.pack(side="left", fill="both", expand=True)
        self._bind_events()
        theme.on_change(lambda _p: self._redraw())

    def _build_header(self) -> None:
        """Crea los títulos de las columnas."""
        m = self._m
        head = ttk.Frame(self, style="Surface.TFrame", padding=(m.px(_PAD), m.px(8)))
        head.pack(fill="x")
        head.columnconfigure(0, weight=1)
        for column, (text, width) in enumerate((("NOMBRE", 0), ("TAMAÑO", _SIZE_W),
                                                ("MODIFICADO", _DATE_W))):
            head.columnconfigure(column, minsize=m.px(width))
            ttk.Label(head, text=text, style="CardCaption.TLabel").grid(
                row=0, column=column, sticky="w" if column == 0 else "e")
        ttk.Separator(self).pack(fill="x")

    def _bind_events(self) -> None:
        """Conecta clics, teclado, rueda del ratón y cambios de tamaño."""
        c = self._canvas
        c.bind("<Configure>", lambda _e: self._redraw())
        c.bind("<Button-1>", self._on_click)
        c.bind("<Double-Button-1>", lambda e: self._open(self._index_at(e.y)))
        c.bind("<Return>", lambda _e: self._open(self._focus))
        c.bind("<Up>", lambda _e: self._move(-1))
        c.bind("<Down>", lambda _e: self._move(1))
        c.bind("<Control-a>", lambda _e: self._select(set(range(len(self._entries)))))
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Button-4>", lambda _e: c.yview_scroll(-1, "units"))
        c.bind("<Button-5>", lambda _e: c.yview_scroll(1, "units"))

    def show(self, entries: Iterable[RemoteEntry]) -> None:
        """Reemplaza el contenido de la lista.

        Args:
            entries (Iterable[RemoteEntry]): Elementos de la carpeta, ya ordenados.
        """
        self._entries = list(entries)
        self._selected.clear()
        self._anchor = self._focus = 0
        self._empty = "Esta carpeta está vacía."
        self._canvas.yview_moveto(0)
        self._redraw()
        self._on_select()

    def clear(self) -> None:
        """Vacía la lista (al desconectar)."""
        self.show(())
        self._empty = "Conecta la PS5 para ver sus archivos."
        self._redraw()

    def selected_entries(self) -> list[RemoteEntry]:
        """Obtiene los elementos seleccionados.

        Returns:
            list[RemoteEntry]: Elementos seleccionados, en el orden de la lista.
        """
        return [self._entries[i] for i in sorted(self._selected)]

    def _index_at(self, y: int) -> int:
        """Calcula la fila bajo una coordenada vertical.

        Args:
            y (int): Coordenada del evento.

        Returns:
            int: Índice de la fila, o ``-1`` si no hay ninguna.
        """
        index = int(self._canvas.canvasy(y) // self._m.px(_ROW))
        return index if 0 <= index < len(self._entries) else -1

    def _on_click(self, event: tk.Event) -> None:
        """Selecciona según el clic y las teclas Ctrl o Mayús.

        Args:
            event (tk.Event): Evento del clic.
        """
        self._canvas.focus_set()
        index = self._index_at(event.y)
        if index < 0:
            self._select(set())
            return
        if event.state & _SHIFT:
            low, high = sorted((self._anchor, index))
            self._select(set(range(low, high + 1)), focus=index, keep_anchor=True)
        elif event.state & _CTRL:
            self._select(self._selected ^ {index}, focus=index)
        else:
            self._select({index}, focus=index)

    def _move(self, delta: int) -> None:
        """Mueve la selección una fila con las flechas.

        Args:
            delta (int): ``-1`` (arriba) o ``1`` (abajo).
        """
        if self._entries:
            index = min(len(self._entries) - 1, max(0, self._focus + delta))
            self._select({index}, focus=index)
            self._canvas.yview_moveto(max(0.0, (index - 3) / len(self._entries)))

    def _select(self, indexes: set[int], focus: int | None = None,
                keep_anchor: bool = False) -> None:
        """Cambia la selección y avisa.

        Args:
            indexes (set[int]): Filas seleccionadas.
            focus (int | None): Fila con el foco del teclado.
            keep_anchor (bool): ``True`` para no mover el inicio de un rango.
        """
        self._selected = indexes
        if focus is not None:
            self._focus = focus
            if not keep_anchor:
                self._anchor = focus
        self._redraw()
        self._on_select()

    def _open(self, index: int) -> None:
        """Abre la fila indicada.

        Args:
            index (int): Fila (``-1`` = ninguna).
        """
        if 0 <= index < len(self._entries):
            self._on_open(self._entries[index])

    def _redraw(self) -> None:
        """Dibuja todas las filas con la paleta actual."""
        c, p, m = self._canvas, self._theme.palette, self._m
        c.delete("all")
        c.configure(background=p.surface)
        width, row = max(c.winfo_width(), 1), m.px(_ROW)
        if not self._entries:
            c.create_text(width / 2, row, text=self._empty, fill=p.muted,
                          font=self._theme.fonts.body)
        for index, entry in enumerate(self._entries):
            self._draw_row(index, entry, width, p)
        c.configure(scrollregion=(0, 0, width, max(row * len(self._entries), 1)))

    def _badge_image(self, width: int, height: int, color: str) -> ImageTk.PhotoImage:
        """Obtiene (y guarda) el fondo redondeado y suavizado de una etiqueta.

        Args:
            width (int): Ancho en píxeles.
            height (int): Alto en píxeles.
            color (str): Color de relleno.

        Returns:
            ImageTk.PhotoImage: Imagen lista para el lienzo.
        """
        key = (width, height, color)
        if key not in self._badges:
            image = render_rounded((width, height), self._m.px(5), color, None)
            self._badges[key] = ImageTk.PhotoImage(image, master=self)
        return self._badges[key]

    def _draw_row(self, index: int, entry: RemoteEntry, width: int, p: Palette) -> None:
        """Dibuja una fila: fondo, icono, nombre, etiqueta, tamaño y fecha.

        Args:
            index (int): Posición de la fila.
            entry (RemoteEntry): Elemento a dibujar.
            width (int): Ancho del lienzo.
            p (Palette): Paleta actual.
        """
        c, m, fonts = self._canvas, self._m, self._theme.fonts
        row, pad = m.px(_ROW), m.px(_PAD)
        top, middle = index * row, index * row + row / 2
        if index in self._selected:
            c.create_rectangle(0, top, width, top + row, fill=p.accent_soft, width=0)
            c.create_rectangle(0, top, m.px(3), top + row, fill=p.accent, width=0)
        c.create_line(0, top + row - 1, width, top + row - 1, fill=p.line)
        icon = self._theme.icons.get("folder" if entry.is_dir else "file", 16, "muted")
        c.create_image(pad, middle, image=icon, anchor="w")
        date_x = width - pad
        size_x = date_x - m.px(_DATE_W)
        x, room = pad + m.px(_ICON_W), size_x - m.px(_SIZE_W) - pad - m.px(_ICON_W) - m.px(12)
        badge = entry_badge(entry)
        badge_w = fonts.small_bold.measure(badge.text) + m.px(14) if badge else 0
        name = elide(entry.name, fonts.body, max(room - badge_w - m.px(10), m.px(40)))
        c.create_text(x, middle, text=name, anchor="w", fill=p.text, font=fonts.body)
        if badge:
            bx = x + fonts.body.measure(name) + m.px(10)
            fill, ink = (getattr(p, a) for a in _BADGE_COLORS[badge.kind])
            c.create_image(bx, middle, image=self._badge_image(badge_w, m.px(18), fill),
                           anchor="w")
            c.create_text(bx + badge_w / 2, middle, text=badge.text, fill=ink,
                          font=fonts.small_bold)
        for text, right in ((presenters.entry_size_text(entry) or "—", size_x),
                            (presenters.modified_text(entry.modified), date_x)):
            c.create_text(right, middle, text=text, anchor="e", fill=p.muted, font=fonts.body)
