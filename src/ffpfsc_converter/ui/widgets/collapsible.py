"""Contenedor que se pliega y se despliega con una animación suave de su alto.

El contenido va en ``inner``, ubicado con ``place`` arriba del marco: el marco
recorta lo que sobra, así que cambiar su alto cuadro a cuadro lo muestra u oculta
de a poco, sin aparecer ni desaparecer de golpe.
"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.ui.theme import ANIMATION_FRAME_MS, ANIMATION_MS


def eased_height(start: int, end: int, progress: float) -> int:
    """Calcula el alto en un momento de la animación, desacelerando al final.

    Args:
        start (int): Alto inicial.
        end (int): Alto final.
        progress (float): Fracción del tiempo transcurrido (se limita a 0-1).

    Returns:
        int: Alto en ese momento; con ``progress >= 1`` es exactamente ``end``.
    """
    t = min(max(progress, 0.0), 1.0)
    return round(start + (end - start) * (1 - (1 - t) ** 3))


class Collapsible(ttk.Frame):
    """Marco plegable: ``expand``/``collapse`` animan su alto hasta mostrar o ocultar ``inner``.

    Attributes:
        inner (ttk.Frame): Donde se ponen los controles.
    """

    def __init__(self, parent: tk.Misc, style: str = "Surface.TFrame") -> None:
        """Crea el marco desplegado.

        Args:
            parent (tk.Misc): Contenedor.
            style (str): Estilo de la superficie sobre la que va.
        """
        super().__init__(parent, style=style, height=1)
        self.inner = ttk.Frame(self, style=style)
        self.inner.place(x=0, y=0, relwidth=1)
        self._expanded = True
        self._job: str | None = None
        self.inner.bind("<Configure>", lambda _e: self._follow_content(), add="+")

    @property
    def is_expanded(self) -> bool:
        """Indica si está desplegado (o desplegándose).

        Returns:
            bool: ``True`` si el contenido queda visible.
        """
        return self._expanded

    def expand(self, animate: bool = True) -> None:
        """Muestra el contenido.

        Args:
            animate (bool): ``False`` para mostrarlo al instante (al construir la vista).
        """
        self._expanded = True
        self._animate_to(self.inner.winfo_reqheight(), animate)

    def collapse(self, animate: bool = True) -> None:
        """Oculta el contenido.

        Args:
            animate (bool): ``False`` para ocultarlo al instante (al construir la vista).
        """
        self._expanded = False
        self._animate_to(0, animate)

    def _animate_to(self, target: int, animate: bool) -> None:
        """Cambia el alto hasta ``target`` en varios cuadros (o de una vez).

        Args:
            target (int): Alto final.
            animate (bool): ``False`` para aplicarlo al instante.
        """
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        start = self.winfo_height()
        began = time.monotonic() - (0 if animate else ANIMATION_MS)
        self._step(start, target, began)

    def _step(self, start: int, target: int, began: float) -> None:
        """Aplica el alto que corresponde al tiempo transcurrido y programa el siguiente.

        La animación se guía por el reloj, no por la cantidad de cuadros: dura lo mismo
        aunque la ventana esté ocupada y algún cuadro llegue tarde.

        Args:
            start (int): Alto al empezar.
            target (int): Alto final.
            began (float): Momento de inicio (``time.monotonic``).
        """
        self._job = None
        progress = (time.monotonic() - began) * 1000 / ANIMATION_MS
        self.configure(height=max(eased_height(start, target, progress), 1))  # 0 = sin alto
        if progress < 1:
            self._job = self.after(ANIMATION_FRAME_MS,
                                   lambda: self._step(start, target, began))

    def _follow_content(self) -> None:
        """Si el contenido cambia de alto (por ejemplo, pasa a otra línea), lo acompaña."""
        if self._expanded and self._job is None:
            self.configure(height=max(self.inner.winfo_reqheight(), 1))
