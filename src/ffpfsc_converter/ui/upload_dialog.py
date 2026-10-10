"""Ventana modal para elegir la carpeta de la PS5 donde subir los juegos comprimidos."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.config import APP_TITLE, PS5_FAVORITE_PATHS, PS5_START_PATH
from ffpfsc_converter.infrastructure.ftp.listing import join_remote
from ffpfsc_converter.ui import theme


class UploadDestinationDialog(tk.Toplevel):
    """Pide la carpeta de destino en la PS5 (por defecto, la que vigila ShadowMount+)."""

    def __init__(self, parent: tk.Misc, names: list[str]) -> None:
        """Construye la ventana modal.

        Args:
            parent (tk.Misc): Ventana principal.
            names (list[str]): Archivos que se subirán, para mostrarlos.
        """
        super().__init__(parent)
        self.title(f"{APP_TITLE} — Subir a la PS5")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result: str | None = None
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        shown = "\n".join(f"• {n}" for n in names[:6])
        more = f"\n… y {len(names) - 6} más" if len(names) > 6 else ""
        ttk.Label(body, text=f"Se subirá a la PS5:\n{shown}{more}", justify="left").pack(
            anchor="w")
        ttk.Label(body, text="Carpeta de destino:").pack(anchor="w", pady=(10, 2))
        self._path = tk.StringVar(value=PS5_START_PATH)
        combo = ttk.Combobox(body, textvariable=self._path, values=list(PS5_FAVORITE_PATHS),
                             width=40)
        combo.pack(anchor="w")
        ttk.Label(body, text="/data/homebrew es la carpeta que vigila ShadowMount+. Si ya existe "
                  "un archivo con el mismo nombre, se reemplazará.", foreground=theme.HINT_FG,
                  wraplength=420, justify="left").pack(anchor="w", pady=(6, 0))
        bar = ttk.Frame(body)
        bar.pack(fill="x", pady=(14, 0))
        ttk.Button(bar, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="⬆ Subir", command=self._accept).pack(side="right", padx=6)
        combo.bind("<Return>", lambda _e: self._accept())
        self.grab_set()

    def ask(self) -> str | None:
        """Muestra la ventana y espera la elección.

        Returns:
            str | None: Carpeta remota absoluta, o ``None`` si se canceló.
        """
        self.wait_window()
        return self.result

    def _accept(self) -> None:
        """Normaliza la ruta elegida y cierra."""
        self.result = join_remote("/", self._path.get().strip() or PS5_START_PATH)
        self.destroy()
