"""Estilos ttk de superficies planas y textos.

Convención de nombres: ``<Superficie><Rol>.TLabel`` (por ejemplo,
``CardMuted.TLabel`` es texto secundario sobre una tarjeta). Los botones,
tarjetas y píldoras redondeados están en :mod:`~ffpfsc_converter.ui.theme.round_styles`.
"""
from __future__ import annotations

from tkinter import ttk

from ffpfsc_converter.ui.theme.fonts import Fonts
from ffpfsc_converter.ui.theme.palette import Palette

#: Superficies sobre las que va texto: prefijo del estilo → atributo de la paleta.
SURFACES = {"": "bg", "Side": "side", "Card": "surface", "Alt": "surface2", "Sel": "accent_soft"}
#: Roles de texto: sufijo del estilo → (atributo de color, atributo de fuente).
TEXT_ROLES = {
    "": ("text", "body"), "Muted": ("muted", "body"), "Small": ("muted", "small"),
    "Bold": ("text", "body_bold"), "Heading": ("text", "heading"), "Title": ("text", "title"),
    "Caption": ("muted", "caption"), "Mono": ("text", "mono"), "MonoMuted": ("muted", "mono"),
    "Accent": ("accent", "body_bold"), "Display": ("text", "display"), "Ok": ("ok", "body_bold"),
    "Warn": ("warn", "body"), "Bad": ("bad", "body"),
}


def apply_base_styles(style: ttk.Style, p: Palette, f: Fonts) -> None:
    """Configura los marcos planos y los textos.

    Args:
        style (ttk.Style): Gestor de estilos de la ventana.
        p (Palette): Paleta del tema.
        f (Fonts): Fuentes de la app.
    """
    _frames(style, p)
    _labels(style, p, f)


def _frames(style: ttk.Style, p: Palette) -> None:
    """Configura los marcos planos de cada superficie.

    Args:
        style (ttk.Style): Gestor de estilos.
        p (Palette): Paleta del tema.
    """
    style.configure("TFrame", background=p.bg)
    style.configure("Side.TFrame", background=p.side)
    style.configure("Surface.TFrame", background=p.surface)
    style.configure("Alt.TFrame", background=p.surface2)
    style.configure("Sel.TFrame", background=p.accent_soft)


def _labels(style: ttk.Style, p: Palette, f: Fonts) -> None:
    """Configura los textos de cada superficie.

    Args:
        style (ttk.Style): Gestor de estilos.
        p (Palette): Paleta del tema.
        f (Fonts): Fuentes de la app.
    """
    for surface, bg_attr in SURFACES.items():
        for role, (fg_attr, font_attr) in TEXT_ROLES.items():
            name = f"{surface}{role}.TLabel" if surface or role else "TLabel"
            style.configure(name, background=getattr(p, bg_attr),
                            foreground=getattr(p, fg_attr), font=getattr(f, font_attr))
