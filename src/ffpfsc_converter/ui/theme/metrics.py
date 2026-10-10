"""Escala de la interfaz según la densidad de la pantalla.

Las fuentes en puntos ya se escalan solas; los márgenes, altos de fila y
tamaños de icono se dan en píxeles lógicos (96 ppp) y se convierten con :meth:`px`.
"""
from __future__ import annotations

import tkinter as tk

_BASE_DPI = 96.0
_MIN_SCALE, _MAX_SCALE = 1.0, 3.0


class Metrics:
    """Convierte medidas lógicas en píxeles reales.

    Attributes:
        scale (float): Factor de escala (1.0 = pantalla de 96 ppp).
    """

    def __init__(self, scale: float) -> None:
        """Guarda el factor de escala.

        Args:
            scale (float): Factor de escala, se limita entre 1 y 3.
        """
        self.scale = min(max(scale, _MIN_SCALE), _MAX_SCALE)

    @classmethod
    def from_root(cls, root: tk.Misc) -> Metrics:
        """Calcula la escala a partir de la resolución que informa Tk.

        Args:
            root (tk.Misc): Ventana raíz.

        Returns:
            Metrics: Métricas de la pantalla.
        """
        return cls(root.winfo_fpixels("1i") / _BASE_DPI)

    def px(self, value: float) -> int:
        """Convierte píxeles lógicos en píxeles de la pantalla.

        Args:
            value (float): Medida a 96 ppp.

        Returns:
            int: Medida escalada y redondeada.
        """
        return round(value * self.scale)
