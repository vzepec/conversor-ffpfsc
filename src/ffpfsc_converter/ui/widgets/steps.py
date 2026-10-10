"""Indicador de pasos numerados unidos por líneas (hecho, actual, pendiente o fallido)."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence

from PIL import ImageTk

from ffpfsc_converter.ui.theme import Palette, ThemeManager
from ffpfsc_converter.ui.theme.shapes import render_circle

_CIRCLE, _GAP, _HEIGHT = 24, 8, 32


class Steps(tk.Canvas):
    """Pasos de un proceso, como «✓ Descarga —— 2 Compresión —— 3 Reemplazo»."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, names: Sequence[str],
                 width: int) -> None:
        """Crea el indicador con todos los pasos pendientes.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            names (Sequence[str]): Nombre de cada paso.
            width (int): Ancho en píxeles lógicos.
        """
        m = theme.metrics
        super().__init__(parent, width=m.px(width), height=m.px(_HEIGHT), highlightthickness=0,
                         bd=0)
        self._theme, self._names = theme, list(names)
        self._states = ["todo"] * len(self._names)
        self._photos: list[ImageTk.PhotoImage] = []  # Tk no guarda referencia a las imágenes
        self.bind("<Configure>", lambda _e: self._draw())
        theme.on_change(lambda _p: self._draw())

    def set_states(self, states: Sequence[str]) -> None:
        """Cambia el estado de cada paso.

        Args:
            states (Sequence[str]): ``"done"``, ``"now"``, ``"failed"`` o ``"todo"`` por paso.
        """
        self._states = list(states)
        self._draw()

    def _draw(self) -> None:
        """Dibuja círculos, nombres y líneas repartiendo el ancho disponible."""
        p, m, fonts = self._theme.palette, self._theme.metrics, self._theme.fonts
        self.delete("all")
        self._photos.clear()
        self.configure(background=p.surface)
        circle, gap, middle = m.px(_CIRCLE), m.px(_GAP), m.px(_HEIGHT) / 2
        widths = [circle + gap + fonts.body_bold.measure(n) for n in self._names]
        free = max(self.winfo_width(), sum(widths)) - sum(widths)
        line = free / max(len(self._names) - 1, 1) - 2 * gap
        x = 0.0
        for index, (name, state) in enumerate(zip(self._names, self._states, strict=True)):
            if index:
                color = p.ok if self._states[index - 1] == "done" else p.line
                self.create_line(x + gap, middle, x + gap + line, middle, fill=color,
                                 width=m.px(2))
                x += line + 2 * gap
            self._circle(x, middle, circle, index, state, p)
            text_color = p.muted if state == "todo" else p.text
            self.create_text(x + circle + gap, middle, text=name, anchor="w", fill=text_color,
                             font=fonts.body_bold)
            x += widths[index]

    def _circle(self, x: float, middle: float, size: int, index: int, state: str,
                p: Palette) -> None:
        """Dibuja el círculo de un paso con su número o símbolo.

        Args:
            x (float): Borde izquierdo.
            middle (float): Centro vertical.
            size (int): Diámetro.
            index (int): Posición del paso (se muestra desde 1).
            state (str): Estado del paso.
            p (Palette): Paleta actual.
        """
        fill, outline, ink, text = {
            "done": (p.ok, p.ok, "#ffffff", "✓"),
            "now": (p.surface, p.accent, p.accent, str(index + 1)),
            "failed": (p.warn, p.warn, "#ffffff", "✕"),
        }.get(state, (p.surface, p.line, p.muted, str(index + 1)))
        m = self._theme.metrics
        halo = (m.px(4), p.accent_soft) if state == "now" else None
        image = render_circle(size, fill, outline, m.px(1.5), halo)
        self._photos.append(ImageTk.PhotoImage(image, master=self))
        self.create_image(x + size / 2, middle, image=self._photos[-1])
        self.create_text(x + size / 2, middle, text=text, fill=ink,
                         font=self._theme.fonts.small_bold)
