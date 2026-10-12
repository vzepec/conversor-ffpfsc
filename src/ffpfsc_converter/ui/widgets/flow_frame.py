"""Contenedor que ubica sus elementos en fila y pasa a la línea siguiente si no caben.

Cada línea es un marco propio: los elementos de una línea quedan uno junto al otro,
sin heredar columnas de las demás (una cuadrícula común las alinearía entre líneas).
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence
from tkinter import ttk


def flow_rows(widths: Sequence[int], available: int, gap: int) -> list[int]:
    """Reparte elementos en líneas, de izquierda a derecha, sin pasar del ancho disponible.

    Args:
        widths (Sequence[int]): Ancho de cada elemento, en orden.
        available (int): Ancho del contenedor.
        gap (int): Separación horizontal entre elementos de una misma línea.

    Returns:
        list[int]: Línea (desde ``0``) de cada elemento. Un elemento más ancho que el
        contenedor ocupa su propia línea.
    """
    rows: list[int] = []
    row = used = 0
    for width in widths:
        if used and used + gap + width > available:
            row, used = row + 1, 0
        used = used + gap + width if used else width
        rows.append(row)
    return rows


class FlowFrame(ttk.Frame):
    """Marco que acomoda sus elementos en líneas según el ancho que tenga."""

    def __init__(self, parent: tk.Misc, gap: int, line_gap: int,
                 style: str = "Surface.TFrame") -> None:
        """Crea el marco vacío.

        Args:
            parent (tk.Misc): Contenedor.
            gap (int): Separación horizontal entre elementos (píxeles reales).
            line_gap (int): Separación vertical entre líneas (píxeles reales).
            style (str): Estilo del marco (el de la superficie sobre la que va).
        """
        super().__init__(parent, style=style)
        self._gap, self._line_gap, self._style = gap, line_gap, style
        self._items: list[tk.Widget] = []
        self._lines: list[ttk.Frame] = []
        self._rows: list[int] = []
        self.bind("<Configure>", lambda _event: self._relayout(), add="+")

    def refresh(self) -> None:
        """Vuelve a repartir todo (por ejemplo, porque un elemento se mostró u ocultó)."""
        self._rows = []
        self._relayout()

    def add(self, item: tk.Widget) -> None:
        """Agrega un elemento (ya creado con este marco como padre) al final.

        Args:
            item (tk.Widget): Elemento a ubicar.
        """
        self._items.append(item)
        self._rows = []
        self._relayout()

    def _relayout(self) -> None:
        """Vuelve a repartir los elementos si cambió la cantidad de líneas necesarias.

        Los elementos ocultos (``is_hidden``) no ocupan lugar, y los que lo indican se
        ubican según su ancho completo (``flow_width``) aunque estén animándose.
        """
        items = [item for item in self._items if not getattr(item, "is_hidden", False)]
        for item in self._items:
            if item not in items:
                item.pack_forget()
        width = self.winfo_width()
        widths = [_full_width(item) for item in items]
        if width <= 1:  # aún sin dibujar: todo en una línea, como pide su tamaño
            width = sum(widths) + self._gap * len(widths)
        rows = flow_rows(widths, width, self._gap)
        if rows == self._rows:
            return
        self._rows = rows
        self._place(items, rows)

    def _place(self, items: list[tk.Widget], rows: list[int]) -> None:
        """Pone cada elemento en el marco de su línea, de izquierda a derecha.

        Args:
            items (list[tk.Widget]): Elementos visibles, en orden.
            rows (list[int]): Línea de cada elemento.
        """
        count = rows[-1] + 1 if rows else 0
        while len(self._lines) < count:
            self._lines.append(ttk.Frame(self, style=self._style))
        for index, line in enumerate(self._lines):
            if index < count:
                line.pack(side="top", anchor="w", pady=(self._line_gap if index else 0, 0))
            else:
                line.pack_forget()
        for row in range(count):
            self._fill_line(self._lines[row],
                            [item for item, r in zip(items, rows, strict=True) if r == row])

    def _fill_line(self, line: ttk.Frame, wanted: list[tk.Widget]) -> None:
        """Deja en una línea exactamente esos elementos, tocando solo los que cambian.

        Volver a ubicar un elemento que no se movió lo hace parpadear un cuadro, así que
        si la línea ya empieza con los elementos correctos solo se agregan los nuevos.

        Args:
            line (ttk.Frame): Marco de la línea.
            wanted (list[tk.Widget]): Elementos de la línea, en orden.
        """
        current = line.pack_slaves()
        if current != wanted:
            self._repack(line, current, wanted)
        for index, item in enumerate(wanted):
            # La separación va a la izquierda (salvo en el primero): así la línea mide
            # justo lo que calcula ``flow_rows`` y el último elemento no queda recortado.
            item.pack_configure(padx=(self._gap if index else 0, 0))

    def _repack(self, line: ttk.Frame, current: list[tk.Widget],
                wanted: list[tk.Widget]) -> None:
        """Agrega a la línea los elementos que faltan (o la rehace si cambió el orden).

        Args:
            line (ttk.Frame): Marco de la línea.
            current (list[tk.Widget]): Elementos que ya tiene, en orden.
            wanted (list[tk.Widget]): Elementos que debe tener, en orden.
        """
        if wanted[:len(current)] == current:
            missing = wanted[len(current):]
        else:
            for item in current:  # pack agrega al final: hay que rehacer el orden
                item.pack_forget()
            missing = wanted
        for item in missing:
            item.pack(in_=line, side="left", fill="y")
            item.lift()  # los marcos de línea se crean después: sin esto los taparían


def _full_width(item: tk.Widget) -> int:
    """Ancho con el que se ubica un elemento: el completo si se está animando.

    Args:
        item (tk.Widget): Elemento del marco.

    Returns:
        int: ``flow_width()`` si lo ofrece; si no, el ancho que pide.
    """
    flow_width = getattr(item, "flow_width", None)
    return flow_width() if callable(flow_width) else item.winfo_reqwidth()
