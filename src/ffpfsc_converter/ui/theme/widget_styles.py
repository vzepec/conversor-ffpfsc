"""Estilos ttk de campos, barras de progreso, barras de desplazamiento, segmentos e interruptores.

Todos usan imágenes redondeadas (ver :mod:`~ffpfsc_converter.ui.theme.round_styles`).
"""
from __future__ import annotations

from tkinter import ttk

from ffpfsc_converter.ui.theme.fonts import Fonts
from ffpfsc_converter.ui.theme.icons import IconSet
from ffpfsc_converter.ui.theme.metrics import Metrics
from ffpfsc_converter.ui.theme.palette import Palette
from ffpfsc_converter.ui.theme.round_styles import VARIANTS, set_corner_color
from ffpfsc_converter.ui.theme.rounded import RoundedImages

_SWITCH_ELEMENT = "Switch.indicator"
#: Barras de progreso → imagen del avance.
BARS = {"Thin": "pbar.accent", "OkThin": "pbar.ok", "WarnThin": "pbar.warn",
        "Big": "pbar.accent"}


def apply_widget_styles(style: ttk.Style, images: RoundedImages, p: Palette, f: Fonts,
                        m: Metrics) -> None:
    """Configura campos, barras y segmentos (crea sus elementos la primera vez).

    Args:
        style (ttk.Style): Gestor de estilos.
        images (RoundedImages): Imágenes redondeadas del tema.
        p (Palette): Paleta del tema.
        f (Fonts): Fuentes de la app.
        m (Metrics): Escala de la pantalla.
    """
    if "Round.trough" not in style.element_names():
        _create_elements(style, images)
    style.configure("TEntry", foreground=p.text, insertcolor=p.text, padding=(m.px(9), m.px(5)),
                    selectbackground=p.accent_soft, selectforeground=p.text)
    style.map("TEntry", foreground=[("disabled", p.muted)])
    set_corner_color(style, "TEntry", p.bg)
    for prefix, attr in VARIANTS.items():
        set_corner_color(style, f"{prefix}.TEntry", getattr(p, attr))
    for name in BARS:
        style.configure(f"{name}.Horizontal.TProgressbar", background=p.surface)
    style.configure("Vertical.TScrollbar", troughcolor=p.surface, background=p.surface,
                    bordercolor=p.surface, lightcolor=p.surface, darkcolor=p.surface,
                    borderwidth=0)
    style.configure("Seg.Toolbutton", foreground=p.muted, font=f.small_bold,
                    padding=(m.px(10), m.px(5)), anchor="center", focuscolor=p.surface2)
    style.map("Seg.Toolbutton", foreground=[("disabled", p.line), ("selected", p.text),
                                            ("active", p.text)])
    set_corner_color(style, "Seg.Toolbutton", p.surface2)
    style.configure("TSeparator", background=p.line)


def _create_elements(style: ttk.Style, images: RoundedImages) -> None:
    """Crea los elementos de imagen y las estructuras de campos, barras y segmentos.

    Args:
        style (ttk.Style): Gestor de estilos.
        images (RoundedImages): Imágenes redondeadas del tema.
    """
    def element(name: str, image: str, *states: tuple[str, str], sticky: str = "nsew") -> None:
        """Crea un elemento de imagen estirable.

        Args:
            name (str): Nombre del elemento.
            image (str): Imagen del estado normal.
            *states (tuple[str, str]): Pares (estado ttk, imagen).
            sticky (str): Cómo se ajusta al espacio disponible.
        """
        extra = [(state, images.get(alt)) for state, alt in states]
        minimum = 2 * images.border(image) + 1  # las imágenes son grandes; el widget no
        style.element_create(name, "image", images.get(image), *extra,
                             border=images.border(image), padding=0, sticky=sticky,
                             width=minimum, height=minimum)

    element("RoundEntry.field", "field", ("focus", "field.focus"))
    style.layout("TEntry", [("RoundEntry.field", {"sticky": "nswe", "children": [
        ("Entry.padding", {"sticky": "nswe", "children": [
            ("Entry.textarea", {"sticky": "nswe"})]})]})])
    element("Round.trough", "trough")
    for name, image in BARS.items():
        element(f"Round{name}.pbar", image)
        style.layout(f"{name}.Horizontal.TProgressbar", [("Round.trough", {
            "sticky": "nswe", "children": [(f"Round{name}.pbar",
                                            {"side": "left", "sticky": "ns"})]})])
    element("Round.Vertical.Scrollbar.thumb", "thumb", ("pressed", "thumb.hover"),
            ("active", "thumb.hover"))
    style.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
        "sticky": "ns", "children": [("Round.Vertical.Scrollbar.thumb",
                                      {"expand": "1", "sticky": "nswe"})]})])
    element("Round.seg", "seg.off", ("selected", "seg.on"))
    style.layout("Seg.Toolbutton", [("Round.seg", {"sticky": "nswe", "children": [
        ("Toolbutton.padding", {"sticky": "nswe", "children": [
            ("Toolbutton.label", {"sticky": "nswe"})]})]})])


def ensure_switch_style(style: ttk.Style, icons: IconSet, p: Palette, f: Fonts,
                        surface: str) -> None:
    """Crea (una vez) el interruptor y lo colorea para la superficie dada.

    Args:
        style (ttk.Style): Gestor de estilos.
        icons (IconSet): Iconos (contiene las imágenes del interruptor).
        p (Palette): Paleta del tema.
        f (Fonts): Fuentes de la app.
        surface (str): Fondo sobre el que va el interruptor.
    """
    if _SWITCH_ELEMENT not in style.element_names():
        style.element_create(_SWITCH_ELEMENT, "image", icons.switch(False),
                             ("selected", icons.switch(True)), border=0, sticky="w")
        children = [(_SWITCH_ELEMENT, {"side": "left", "sticky": ""}),
                    ("Checkbutton.label", {"side": "left", "sticky": "w"})]
        style.layout("Switch.TCheckbutton",
                     [("Checkbutton.padding", {"sticky": "nswe", "children": children})])
    style.configure("Switch.TCheckbutton", background=surface, foreground=p.text, font=f.body,
                    padding=(0, 2), focuscolor=surface)
    style.map("Switch.TCheckbutton", background=[("active", surface)])
