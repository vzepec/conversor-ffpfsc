"""Contenedor que ubica sus elementos en fila y pasa a la línea siguiente si no caben."""
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
        self._gap, self._line_gap = gap, line_gap
        self._items: list[tk.Widget] = []
        self._rows: list[int] = []
        self.bind("<Configure>", lambda _event: self._relayout(), add="+")

    def add(self, item: tk.Widget) -> None:
        """Agrega un elemento (ya creado con este marco como padre) al final.

        Args:
            item (tk.Widget): Elemento a ubicar.
        """
        self._items.append(item)
        self._rows = []
        self._relayout()

    def _relayout(self) -> None:
        """Vuelve a repartir los elementos si cambió la cantidad de líneas necesarias."""
        width = self.winfo_width()
        widths = [item.winfo_reqwidth() for item in self._items]
        if width <= 1:  # aún sin dibujar: todo en una línea, como pide su tamaño
            width = sum(widths) + self._gap * len(widths)
        rows = flow_rows(widths, width, self._gap)
        if rows == self._rows:
            return
        self._rows = rows
        column = 0
        for index, (item, row) in enumerate(zip(self._items, rows, strict=True)):
            column = column + 1 if index and row == rows[index - 1] else 0
            item.grid(row=row, column=column, sticky="nsw", padx=(0, self._gap),
                      pady=(self._line_gap if row else 0, 0))
