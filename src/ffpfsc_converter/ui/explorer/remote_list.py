"""Lista de archivos y carpetas de la carpeta remota abierta."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable
from tkinter import ttk

from ffpfsc_converter.domain.remote import RemoteEntry
from ffpfsc_converter.ui.explorer import presenters

_COLUMNS = (
    # (id, encabezado, ancho, alineación)
    ("name", "Nombre", 520, "w"),
    ("size", "Tamaño", 110, "e"),
    ("modified", "Modificado", 150, "w"),
)


class RemoteList(ttk.Frame):
    """Tabla con el contenido de una carpeta de la PS5 y barra de desplazamiento."""

    def __init__(self, parent: tk.Misc, on_open: Callable[[RemoteEntry], None]) -> None:
        """Crea la tabla.

        Args:
            parent (tk.Misc): Contenedor.
            on_open (Callable[[RemoteEntry], None]): Se llama al hacer doble clic en un elemento.
        """
        super().__init__(parent)
        self._entries: dict[str, RemoteEntry] = {}
        self._tree = ttk.Treeview(self, columns=[c[0] for c in _COLUMNS], show="headings",
                                  selectmode="extended")
        for col_id, heading, width, anchor in _COLUMNS:
            self._tree.heading(col_id, text=heading)
            self._tree.column(col_id, width=width, anchor=anchor)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._tree.bind("<Double-1>", lambda _e: self._open_focused(on_open))
        self._tree.bind("<Return>", lambda _e: self._open_focused(on_open))

    def show(self, entries: Iterable[RemoteEntry]) -> None:
        """Reemplaza el contenido de la tabla.

        Args:
            entries (Iterable[RemoteEntry]): Elementos de la carpeta, ya ordenados.
        """
        self._tree.delete(*self._tree.get_children())
        self._entries.clear()
        for entry in entries:
            row = self._tree.insert("", "end", values=(
                presenters.entry_label(entry),
                presenters.entry_size_text(entry),
                presenters.modified_text(entry.modified),
            ))
            self._entries[row] = entry

    def clear(self) -> None:
        """Vacía la tabla (al desconectar)."""
        self.show(())

    def selected_entries(self) -> list[RemoteEntry]:
        """Obtiene los elementos seleccionados.

        Returns:
            list[RemoteEntry]: Elementos seleccionados, en el orden de la tabla.
        """
        return [self._entries[row] for row in self._tree.selection() if row in self._entries]

    def _open_focused(self, on_open: Callable[[RemoteEntry], None]) -> None:
        """Abre el elemento con el foco.

        Args:
            on_open (Callable[[RemoteEntry], None]): Acción a ejecutar con el elemento.
        """
        entry = self._entries.get(self._tree.focus())
        if entry is not None:
            on_open(entry)
