"""Tabla con los juegos de la cola."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable
from tkinter import ttk

TITLE = "titulo"
SOURCE = "juego"
SIZE = "tamano"
ESTIMATE = "estimado"
STATUS = "estado"

_COLUMNS = (
    # (id, encabezado, ancho, alineación)
    (TITLE, "Nombre del juego", 340, "w"),
    (SOURCE, "Carpeta / archivo", 160, "w"),
    (SIZE, "Tamaño", 90, "e"),
    (ESTIMATE, "Peso final estimado", 170, "e"),
    (STATUS, "Estado", 220, "w"),
)


class JobTable(ttk.Treeview):
    """Tabla de trabajos; cada fila se identifica con el ``id`` del trabajo."""

    def __init__(self, parent: tk.Misc) -> None:
        """Crea la tabla con sus columnas.

        Args:
            parent (tk.Misc): Contenedor de la tabla.
        """
        super().__init__(parent, columns=[c[0] for c in _COLUMNS], show="headings", height=6)
        for col_id, heading, width, anchor in _COLUMNS:
            self.heading(col_id, text=heading)
            self.column(col_id, width=width, anchor=anchor)

    def add_row(self, row_id: str, values: dict[str, str]) -> None:
        """Agrega una fila al final.

        Args:
            row_id (str): Identificador de la fila (el ``id`` del trabajo).
            values (dict[str, str]): Columna → texto inicial.
        """
        self.insert("", "end", iid=row_id, values=[values.get(c[0], "") for c in _COLUMNS])

    def set_cell(self, row_id: str, column: str, value: str) -> None:
        """Cambia el texto de una celda si la fila sigue existiendo.

        Args:
            row_id (str): Identificador de la fila.
            column (str): Columna (``TITLE``, ``SIZE``, ``ESTIMATE``…).
            value (str): Nuevo texto.
        """
        if self.exists(row_id):
            self.set(row_id, column, value)

    def selected_ids(self) -> set[str]:
        """Obtiene las filas seleccionadas.

        Returns:
            set[str]: Identificadores de las filas seleccionadas.
        """
        return set(self.selection())

    def delete_rows(self, row_ids: Iterable[str]) -> None:
        """Elimina varias filas.

        Args:
            row_ids (Iterable[str]): Identificadores de las filas a eliminar.
        """
        for row_id in row_ids:
            self.delete(row_id)
