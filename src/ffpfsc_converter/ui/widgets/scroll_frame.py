"""Contenedor con desplazamiento vertical (rueda del ratón en Linux y Windows)."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.ui.theme import Palette, ThemeManager

_WHEEL_UNITS = 120  # Windows y macOS informan múltiplos de 120 por paso


class ScrollFrame(ttk.Frame):
    """Marco cuyo contenido (``inner``) se desplaza verticalmente.

    Attributes:
        inner (ttk.Frame): Contenedor donde se agregan los widgets.
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager, surface: str = "surface") -> None:
        """Crea el lienzo, el contenedor interior y la barra de desplazamiento.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema (para el color de fondo del lienzo).
            surface (str): Atributo de la paleta del fondo.
        """
        super().__init__(parent, style="Surface.TFrame" if surface == "surface" else "TFrame")
        self._surface = surface
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0,
                                 background=getattr(theme.palette, surface))
        self._bar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self.inner = ttk.Frame(self._canvas, style="Surface.TFrame")
        self._window = self._canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self._canvas.configure(yscrollcommand=autohide(self._bar))
        self._canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", self._on_inner_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        for widget in (self._canvas, self.inner):
            widget.bind("<Enter>", self._bind_wheel)
            widget.bind("<Leave>", self._unbind_wheel)
        theme.on_change(self._on_theme)

    def scroll_to_top(self) -> None:
        """Vuelve al principio del contenido."""
        self._canvas.yview_moveto(0)

    def scroll_to_end(self) -> None:
        """Muestra el final del contenido (por ejemplo, la última fila agregada)."""
        self.update_idletasks()
        self._canvas.yview_moveto(1)

    def _on_inner_resize(self, _event: tk.Event) -> None:
        """Ajusta la zona desplazable al tamaño del contenido.

        Args:
            _event (tk.Event): Evento de cambio de tamaño.
        """
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event: tk.Event) -> None:
        """Hace que el contenido ocupe todo el ancho visible.

        Args:
            event (tk.Event): Evento de cambio de tamaño del lienzo.
        """
        self._canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, _event: tk.Event) -> None:
        """Activa la rueda del ratón mientras el puntero está encima.

        Args:
            _event (tk.Event): Evento de entrada del puntero.
        """
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)
        self._canvas.bind_all("<Button-4>", self._on_wheel)
        self._canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _event: tk.Event) -> None:
        """Desactiva la rueda al salir el puntero.

        Args:
            _event (tk.Event): Evento de salida del puntero.
        """
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._canvas.unbind_all(sequence)

    def _on_wheel(self, event: tk.Event) -> None:
        """Desplaza el contenido según la rueda (Windows usa delta, Linux botones 4/5).

        Args:
            event (tk.Event): Evento de la rueda.
        """
        if self.inner.winfo_reqheight() <= self._canvas.winfo_height():
            return
        if getattr(event, "num", None) in (4, 5):
            steps = -1 if event.num == 4 else 1
        else:
            steps = -int(event.delta / _WHEEL_UNITS) or (-1 if event.delta > 0 else 1)
        self._canvas.yview_scroll(steps, "units")

    def _on_theme(self, palette: Palette) -> None:
        """Repinta el fondo del lienzo con la paleta nueva.

        Args:
            palette (Palette): Paleta nueva.
        """
        self._canvas.configure(background=getattr(palette, self._surface))


def autohide(bar: ttk.Scrollbar) -> Callable[[str, str], None]:
    """Crea un ``yscrollcommand`` que muestra la barra solo si el contenido no cabe.

    La barra debe ser hija del mismo contenedor que el widget desplazable, que se
    ubica con ``pack(side="left")``.

    Args:
        bar (ttk.Scrollbar): Barra de desplazamiento vertical.

    Returns:
        Callable[[str, str], None]: Función para ``yscrollcommand``.
    """
    def update(first: str, last: str) -> None:
        """Mueve la barra y la oculta si todo el contenido está a la vista.

        Args:
            first (str): Fracción visible inicial.
            last (str): Fracción visible final.
        """
        if float(first) <= 0.0 and float(last) >= 1.0:
            bar.pack_forget()
        elif not bar.winfo_ismapped():
            bar.pack(side="right", fill="y")
        bar.set(first, last)

    return update
