"""Tipografía: elige la mejor fuente disponible en cada sistema y define los tamaños.

Windows trae Segoe UI; en Linux se usa Noto Sans, Ubuntu o Cantarell según el
escritorio. Si ninguna está, se usa la fuente por defecto de Tk.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Iterable
from dataclasses import dataclass

#: Preferencia de fuentes de interfaz, de mejor a peor (la primera instalada gana).
UI_FAMILIES = ("Segoe UI", "Noto Sans", "Ubuntu", "Cantarell", "SF Pro Text",
               "Helvetica Neue", "DejaVu Sans", "Liberation Sans")
#: Preferencia de fuentes monoespaciadas (rutas, IP, registro).
MONO_FAMILIES = ("Cascadia Mono", "Consolas", "JetBrains Mono", "Noto Sans Mono",
                 "Ubuntu Mono", "DejaVu Sans Mono", "Liberation Mono")


def pick_family(preferred: Iterable[str], available: Iterable[str], fallback: str) -> str:
    """Elige la primera fuente preferida que esté instalada.

    Args:
        preferred (Iterable[str]): Familias en orden de preferencia.
        available (Iterable[str]): Familias instaladas.
        fallback (str): Familia a usar si no hay ninguna preferida.

    Returns:
        str: Nombre de la familia elegida.
    """
    installed = {name.lower(): name for name in available}
    for family in preferred:
        if family.lower() in installed:
            return installed[family.lower()]
    return fallback


@dataclass(frozen=True)
class Fonts:
    """Fuentes con nombre usadas por los estilos.

    Attributes:
        body (tkfont.Font): Texto normal.
        body_bold (tkfont.Font): Texto normal en negrita.
        small (tkfont.Font): Texto secundario.
        small_bold (tkfont.Font): Texto secundario en negrita (píldoras).
        caption (tkfont.Font): Etiquetas en mayúsculas de los campos.
        heading (tkfont.Font): Títulos de tarjetas y filas.
        title (tkfont.Font): Título de cada vista.
        display (tkfont.Font): Números grandes (porcentaje del pipeline).
        mono (tkfont.Font): Rutas, IP y registro técnico.
    """

    body: tkfont.Font
    body_bold: tkfont.Font
    small: tkfont.Font
    small_bold: tkfont.Font
    caption: tkfont.Font
    heading: tkfont.Font
    title: tkfont.Font
    display: tkfont.Font
    mono: tkfont.Font


def create_fonts(root: tk.Misc) -> Fonts:
    """Crea las fuentes de la app y las fija como fuentes por defecto de Tk.

    Args:
        root (tk.Misc): Ventana raíz (las fuentes con nombre pertenecen a ella).

    Returns:
        Fonts: Fuentes creadas.
    """
    available = tkfont.families(root)
    default_family = tkfont.nametofont("TkDefaultFont", root).actual("family")
    ui = pick_family(UI_FAMILIES, available, default_family)
    mono = pick_family(MONO_FAMILIES, available, "TkFixedFont")

    def make(size: int, weight: str = "normal", family: str = ui) -> tkfont.Font:
        """Crea una fuente de la familia elegida.

        Args:
            size (int): Tamaño en puntos.
            weight (str): ``"normal"`` o ``"bold"``.
            family (str): Familia.

        Returns:
            tkfont.Font: Fuente creada.
        """
        return tkfont.Font(root, family=family, size=size, weight=weight)

    fonts = Fonts(body=make(10), body_bold=make(10, "bold"), small=make(9),
                  small_bold=make(9, "bold"), caption=make(8, "bold"),
                  heading=make(11, "bold"), title=make(16, "bold"), display=make(24, "bold"),
                  mono=make(9, family=mono))
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name, root).configure(family=ui, size=10)
    tkfont.nametofont("TkFixedFont", root).configure(family=mono, size=9)
    return fonts
