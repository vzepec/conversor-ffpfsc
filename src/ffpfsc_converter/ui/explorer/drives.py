"""Tarjetas de las unidades de la PS5 (interna, USB y ampliada) con su barra de uso."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence
from tkinter import ttk

from ffpfsc_converter.ui.explorer.view_presenters import DriveCard
from ffpfsc_converter.ui.theme import ThemeManager


class _DriveTile(ttk.Frame):
    """Tarjeta de una unidad."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Crea los widgets vacíos.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
        """
        m = theme.metrics
        super().__init__(parent, style="Card.TFrame", padding=(m.px(13), m.px(11)))
        self._theme = theme
        head = ttk.Frame(self, style="Surface.TFrame")
        head.pack(fill="x")
        self._icon = ttk.Label(head, style="Card.TLabel")
        self._icon.pack(side="left")
        self._name = ttk.Label(head, style="CardBold.TLabel")
        self._name.pack(side="left", padx=(m.px(8), 0))
        self._path = ttk.Label(head, style="CardMonoMuted.TLabel")
        self._path.pack(side="right")
        self._bar = ttk.Progressbar(self, maximum=100, style="Thin.Horizontal.TProgressbar")
        self._bar.pack(fill="x", pady=(m.px(8), m.px(7)))
        self._text = ttk.Label(self, style="CardSmall.TLabel")
        self._text.pack(anchor="w")

    def show(self, card: DriveCard) -> None:
        """Muestra los datos de una unidad.

        Args:
            card (DriveCard): Datos de la tarjeta.
        """
        role = "text" if card.is_available else "muted"
        self._icon.configure(image=self._theme.icons.get(card.icon, 16, role))
        self._name.configure(text=card.name,
                             style="CardBold.TLabel" if card.is_available else "CardMuted.TLabel")
        self._path.configure(text=card.path)
        style = "WarnThin" if card.is_full else "Thin"
        self._bar.configure(value=card.percent, style=f"{style}.Horizontal.TProgressbar")
        self._text.configure(text=card.text)


class DriveStrip(ttk.Frame):
    """Fila de tarjetas de unidades, todas del mismo ancho."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager) -> None:
        """Crea la fila vacía.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
        """
        super().__init__(parent, style="TFrame")
        self._theme = theme
        self._tiles: list[_DriveTile] = []

    def show(self, cards: Sequence[DriveCard]) -> None:
        """Muestra una tarjeta por unidad (crea o quita tarjetas si cambió la cantidad).

        Args:
            cards (Sequence[DriveCard]): Unidades a mostrar, en orden.
        """
        gap = self._theme.metrics.px(10)
        while len(self._tiles) > len(cards):
            self._tiles.pop().destroy()
            self.columnconfigure(len(self._tiles), weight=0, uniform="")
        while len(self._tiles) < len(cards):
            self._tiles.append(_DriveTile(self, self._theme))
        for column, (tile, card) in enumerate(zip(self._tiles, cards, strict=True)):
            self.columnconfigure(column, weight=1, uniform="drive")
            tile.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else gap, 0))
            tile.show(card)
