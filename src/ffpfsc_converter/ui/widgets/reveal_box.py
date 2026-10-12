"""Caja que aparece y desaparece con una animación breve, sin saltos.

El contenido va en ``inner``, ubicado con ``place`` en la esquina superior izquierda;
la caja cambia de ancho y alto cuadro a cuadro y recorta lo que sobra, así que se
encoge hasta desaparecer o crece hasta mostrarse completa. Dentro de un
:class:`~ffpfsc_converter.ui.widgets.flow_frame.FlowFrame` se ubica según su tamaño
final (``flow_width``), de modo que no cambia de línea a mitad de la animación.
"""
from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.ui.theme import ANIMATION_FRAME_MS, ANIMATION_MS


def eased(start: float, end: float, progress: float) -> float:
    """Calcula un valor intermedio de la animación, desacelerando al final.

    Args:
        start (float): Valor inicial.
        end (float): Valor final.
        progress (float): Fracción del tiempo transcurrido (se limita a 0-1).

    Returns:
        float: Valor en ese momento; con ``progress >= 1`` es exactamente ``end``.
    """
    t = min(max(progress, 0.0), 1.0)
    return end if t >= 1 else start + (end - start) * (1 - (1 - t) ** 3)


class RevealBox(ttk.Frame):
    """Caja que se muestra u oculta encogiéndose o creciendo hacia su esquina.

    Attributes:
        inner (ttk.Frame): Donde se ponen los controles.
        is_hidden (bool): ``True`` cuando terminó de ocultarse (no ocupa lugar).
    """

    def __init__(self, parent: tk.Misc, on_visibility: Callable[[], None],
                 style: str = "Surface.TFrame") -> None:
        """Crea la caja visible.

        Args:
            parent (tk.Misc): Contenedor.
            on_visibility (Callable[[], None]): Se llama al empezar a mostrarse y al
                terminar de ocultarse (para que el contenedor la incluya o la quite).
            style (str): Estilo de la superficie sobre la que va.
        """
        super().__init__(parent, style=style, width=1, height=1)
        self.inner = ttk.Frame(self, style=style)
        self.inner.place(x=0, y=0)
        self.is_hidden = False
        self._fraction, self._job = 1.0, None
        self._on_visibility = on_visibility
        self.inner.bind("<Configure>", lambda _e: self._apply(), add="+")

    def flow_width(self) -> int:
        """Ancho completo del contenido, para ubicarla sin importar la animación.

        Returns:
            int: Ancho que pide el contenido.
        """
        return self.inner.winfo_reqwidth()

    def show(self, animate: bool = True) -> None:
        """Muestra la caja creciendo desde su esquina.

        Args:
            animate (bool): ``False`` para mostrarla al instante.
        """
        if self.is_hidden:
            self.is_hidden = False
            self._on_visibility()
        self._animate_to(1.0, animate)

    def hide(self, animate: bool = True) -> None:
        """Oculta la caja encogiéndola hacia su esquina.

        Args:
            animate (bool): ``False`` para ocultarla al instante (al construir la vista).
        """
        self._animate_to(0.0, animate)

    def _animate_to(self, target: float, animate: bool) -> None:
        """Lleva la fracción visible hasta ``target`` guiándose por el reloj.

        Args:
            target (float): ``1`` = completa, ``0`` = oculta.
            animate (bool): ``False`` para aplicarlo al instante.
        """
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        began = time.monotonic() - (0 if animate else ANIMATION_MS)
        self._step(self._fraction, target, began)

    def _step(self, start: float, target: float, began: float) -> None:
        """Aplica la fracción que corresponde al tiempo transcurrido y sigue si falta.

        Args:
            start (float): Fracción al empezar.
            target (float): Fracción final.
            began (float): Momento de inicio (``time.monotonic``).
        """
        self._job = None
        progress = (time.monotonic() - began) * 1000 / ANIMATION_MS
        self._fraction = eased(start, target, progress)
        self._apply()
        if progress < 1:
            self._job = self.after(ANIMATION_FRAME_MS,
                                   lambda: self._step(start, target, began))
        elif target == 0 and not self.is_hidden:
            self.is_hidden = True
            self._on_visibility()

    def _apply(self) -> None:
        """Ajusta el tamaño de la caja a la fracción visible del contenido."""
        width = round(self.inner.winfo_reqwidth() * self._fraction)
        height = round(self.inner.winfo_reqheight() * self._fraction)
        self.configure(width=max(width, 1), height=max(height, 1))  # 0 = «sin tamaño fijo»
