"""Selector numérico «− valor +» de esquinas redondeadas."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.ui.theme import ThemeManager


class Stepper(ttk.Frame):
    """Número entero entre un mínimo y un máximo, con botones para restar y sumar."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, variable: tk.IntVar,
                 limits: tuple[int, int], surface: str = "Card") -> None:
        """Crea el selector.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            variable (tk.IntVar): Variable con el valor elegido.
            limits (tuple[int, int]): Valores mínimo y máximo.
            surface (str): Superficie sobre la que va (``"Card"`` o ``""``).
        """
        style = f"{surface}.Field.TFrame" if surface else "Field.TFrame"
        super().__init__(parent, style=style, padding=2)
        self._variable, (self._minimum, self._maximum) = variable, limits
        width = len(f"{self._maximum} de {self._maximum}")
        self._minus = ttk.Button(self, text="−", width=2, style="Alt.SmallFlat.TButton",
                                 command=lambda: self._step(-1), takefocus=False)
        self._label = ttk.Label(self, style="Alt.TLabel", width=width, anchor="center")
        self._plus = ttk.Button(self, text="+", width=2, style="Alt.SmallFlat.TButton",
                                command=lambda: self._step(1), takefocus=False)
        for widget in (self._minus, self._label, self._plus):
            widget.pack(side="left")
        variable.trace_add("write", lambda *_args: self._render())
        self._render()

    def _step(self, delta: int) -> None:
        """Suma o resta una unidad sin salir de los límites.

        Args:
            delta (int): ``1`` o ``-1``.
        """
        value = min(self._maximum, max(self._minimum, self._value() + delta))
        self._variable.set(value)

    def _value(self) -> int:
        """Lee el valor actual.

        Returns:
            int: Valor de la variable, o el máximo si no es un número válido.
        """
        try:
            return int(self._variable.get())
        except (tk.TclError, ValueError):
            return self._maximum

    def _render(self) -> None:
        """Muestra el valor y deshabilita el botón del límite alcanzado."""
        value = self._value()
        self._label.configure(text=f"{value} de {self._maximum}")
        self._minus.state(["disabled"] if value <= self._minimum else ["!disabled"])
        self._plus.state(["disabled"] if value >= self._maximum else ["!disabled"])
