"""Ventana modal para elegir la carpeta de la PS5 donde subir los juegos comprimidos."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.config import PS5_FAVORITE_PATHS, PS5_START_PATH
from ffpfsc_converter.infrastructure.ftp.listing import join_remote
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.modal import Modal

_SHOWN_NAMES = 6


class UploadDestinationDialog(Modal):
    """Pide la carpeta de destino en la PS5 (por defecto, la que vigila ShadowMount+)."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, names: list[str]) -> None:
        """Construye la ventana modal.

        Args:
            parent (tk.Misc): Ventana principal.
            theme (ThemeManager): Tema.
            names (list[str]): Archivos que se subirán, para mostrarlos.
        """
        count = f"{len(names)} juego" + ("s" if len(names) != 1 else "")
        super().__init__(parent, theme, "Subir a la PS5", count)
        m = theme.metrics
        self.result: str | None = None
        shown = "\n".join(names[:_SHOWN_NAMES])
        more = f"\n… y {len(names) - _SHOWN_NAMES} más" if len(names) > _SHOWN_NAMES else ""
        ttk.Label(self.body, text=shown + more, style="Card.TLabel", justify="left").pack(
            anchor="w")
        ttk.Label(self.body, text="CARPETA DE DESTINO", style="CardCaption.TLabel").pack(
            anchor="w", pady=(m.px(14), m.px(4)))
        row = ttk.Frame(self.body, style="Surface.TFrame")
        row.pack(fill="x")
        self._path = tk.StringVar(value=PS5_START_PATH)
        entry = ttk.Entry(row, textvariable=self._path, width=34, style="Card.TEntry",
                          font=theme.fonts.mono)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _e: self._accept())
        self._quick = ttk.Button(row, text="Accesos rápidos ▾", style="Card.Small.TButton",
                                 command=self._show_menu)
        self._quick.pack(side="left", padx=(m.px(8), 0))
        self._menu = tk.Menu(self, tearoff=False, background=theme.palette.surface,
                             foreground=theme.palette.text, font=theme.fonts.mono,
                             activebackground=theme.palette.accent_soft,
                             activeforeground=theme.palette.text)
        for path in PS5_FAVORITE_PATHS:
            self._menu.add_command(label=path, command=lambda p=path: self._path.set(p))
        ttk.Label(self.body, text="/data/homebrew es la carpeta que vigila ShadowMount+. Si ya "
                  "existe un archivo con el mismo nombre, se reemplazará.",
                  style="CardMuted.TLabel", wraplength=m.px(440), justify="left").pack(
            anchor="w", pady=(m.px(8), 0))
        self.add_button("Subir", self._accept, "Card.Accent.TButton")
        self.add_button("Cancelar", self.destroy)
        self.show_modal()

    def ask(self) -> str | None:
        """Muestra la ventana y espera la elección.

        Returns:
            str | None: Carpeta remota absoluta, o ``None`` si se canceló.
        """
        self.wait_window()
        return self.result

    def _show_menu(self) -> None:
        """Despliega los accesos rápidos bajo su botón."""
        self._menu.tk_popup(self._quick.winfo_rootx(),
                            self._quick.winfo_rooty() + self._quick.winfo_height())

    def _accept(self) -> None:
        """Normaliza la ruta elegida y cierra."""
        self.result = join_remote("/", self._path.get().strip() or PS5_START_PATH)
        self.destroy()
