"""Estilos ttk con esquinas redondeadas: botones, tarjetas, píldoras y etiquetas de icono.

Cada estilo usa una imagen de :mod:`~ffpfsc_converter.ui.theme.rounded` que ttk
estira en 9 partes. Las esquinas transparentes muestran el color ``background``
del estilo, por eso cada estilo tiene variantes por superficie con nombre
``<Superficie>.<Estilo>`` (por ejemplo ``Card.Accent.TButton`` sobre una tarjeta);
ttk hereda todo lo demás del estilo base.
"""
from __future__ import annotations

from tkinter import ttk

from ffpfsc_converter.ui.theme.fonts import Fonts
from ffpfsc_converter.ui.theme.metrics import Metrics
from ffpfsc_converter.ui.theme.palette import Palette
from ffpfsc_converter.ui.theme.rounded import RoundedImages

#: Superficies sobre las que puede ir un widget redondeado → atributo de la paleta.
VARIANTS = {"Card": "surface", "Alt": "surface2", "Side": "side", "Sel": "accent_soft"}
#: Estilos de botón → (imagen, rol de texto, fuente, es pequeño).
BUTTONS = {
    "TButton": ("btn", "text", "body", False),
    "Accent.TButton": ("accent", "accent_ink", "body_bold", False),
    "Ghost.TButton": ("ghost", "text", "body", False),
    "Danger.TButton": ("danger", "bad", "body", False),
    "Flat.TButton": ("flat", "muted", "body", False),
    "Small.TButton": ("btn", "text", "small", True),
    "SmallAccent.TButton": ("accent", "accent_ink", "small_bold", True),
    "SmallGhost.TButton": ("ghost", "text", "small", True),
    "SmallDanger.TButton": ("danger", "bad", "small", True),
    "SmallFlat.TButton": ("flat", "muted", "small_bold", True),
}
#: Marcos redondeados → imagen.
FRAMES = {"Card.TFrame": "card", "Bar.TFrame": "bar", "NavOn.TFrame": "nav",
          "SegBox.TFrame": "segbox", "Field.TFrame": "field", "Path.TFrame": "path"}
#: Píldoras → (imagen, color del texto).
PILLS = {"PillWait": ("pill.wait", "muted"), "PillRun": ("pill.run", "accent"),
         "PillOk": ("pill.ok", "ok"), "PillWarn": ("pill.warn", "warn"),
         "PillBad": ("pill.bad", "bad")}
_STATES = (("disabled", "off"), ("pressed", "pressed"), ("active", "hover"))


def apply_round_styles(style: ttk.Style, images: RoundedImages, p: Palette, f: Fonts,
                       m: Metrics) -> None:
    """Crea (la primera vez) y colorea los estilos redondeados.

    Args:
        style (ttk.Style): Gestor de estilos.
        images (RoundedImages): Imágenes redondeadas del tema.
        p (Palette): Paleta del tema.
        f (Fonts): Fuentes de la app.
        m (Metrics): Escala de la pantalla.
    """
    if "Round.card" not in style.element_names():
        _create_elements(style, images)
        _create_layouts(style)
    _buttons(style, p, f, m)
    for name in FRAMES:
        _with_variants(style, name, p)
    for name, (_image, fg) in PILLS.items():
        style.configure(f"{name}.TLabel", foreground=getattr(p, fg), font=f.small_bold,
                        padding=(m.px(9), m.px(2)))
        _with_variants(style, f"{name}.TLabel", p)
    style.configure("Badge.TLabel", padding=m.px(10))
    _with_variants(style, "Badge.TLabel", p)
    style.configure("Link.TButton", foreground=p.accent, font=f.body_bold, padding=0, width=0)
    style.map("Link.TButton", foreground=[("disabled", p.muted), ("active", p.accent_hover)])
    _with_variants(style, "Link.TButton", p)


def _with_variants(style: ttk.Style, name: str, p: Palette) -> None:
    """Configura el fondo de un estilo y de sus variantes por superficie.

    Args:
        style (ttk.Style): Gestor de estilos.
        name (str): Estilo base (sus esquinas quedan sobre el fondo de la ventana).
        p (Palette): Paleta del tema.
    """
    set_corner_color(style, name, p.bg)
    for prefix, attr in VARIANTS.items():
        set_corner_color(style, f"{prefix}.{name}", getattr(p, attr))


def set_corner_color(style: ttk.Style, name: str, color: str) -> None:
    """Fija el color de las esquinas de un estilo en todos sus estados.

    «clam» cambia el fondo de los botones y campos al pasar el puntero, al
    pulsarlos o al deshabilitarlos; sin esto, las esquinas se verían de otro color.

    Args:
        style (ttk.Style): Gestor de estilos.
        name (str): Estilo.
        color (str): Color de la superficie sobre la que va el widget.
    """
    states = ("disabled", "pressed", "active", "readonly", "focus", "selected", "alternate")
    style.configure(name, background=color, fieldbackground=color)
    style.map(name, background=[(state, color) for state in states],
              fieldbackground=[(state, color) for state in states])


def _image_element(style: ttk.Style, name: str, images: RoundedImages, base: str,
                   states: tuple[tuple[str, str], ...] = ()) -> None:
    """Crea un elemento de imagen estirable en 9 partes.

    Args:
        style (ttk.Style): Gestor de estilos.
        name (str): Nombre del elemento.
        images (RoundedImages): Imágenes del tema.
        base (str): Imagen del estado normal.
        states (tuple[tuple[str, str], ...]): Pares (estado ttk, imagen).
    """
    specs = [(state, images.get(image)) for state, image in states]
    minimum = 2 * images.border(base) + 1  # las imágenes son grandes; el widget no
    style.element_create(name, "image", images.get(base), *specs, border=images.border(base),
                         padding=0, sticky="nsew", width=minimum, height=minimum)


def _create_elements(style: ttk.Style, images: RoundedImages) -> None:
    """Crea los elementos de imagen de botones, marcos, píldoras y la etiqueta de icono.

    Args:
        style (ttk.Style): Gestor de estilos.
        images (RoundedImages): Imágenes del tema.
    """
    for kind in {spec[0] for spec in BUTTONS.values()}:
        _image_element(style, f"Round.{kind}", images, kind,
                       tuple((state, f"{kind}.{suffix}") for state, suffix in _STATES))
    for image in set(FRAMES.values()) | {"badge"}:
        _image_element(style, f"Round.{image}", images, image)
    for image, _fg in PILLS.values():
        _image_element(style, f"Round.{image}", images, image)


def _create_layouts(style: ttk.Style) -> None:
    """Define la estructura de cada estilo redondeado.

    Args:
        style (ttk.Style): Gestor de estilos.
    """
    for name, (image, *_rest) in BUTTONS.items():
        style.layout(name, [(f"Round.{image}", {"sticky": "nswe", "children": [
            ("Button.padding", {"sticky": "nswe", "children": [
                ("Button.label", {"sticky": "nswe"})]})]})])
    style.layout("Link.TButton", [("Button.padding", {"sticky": "nswe", "children": [
        ("Button.label", {"sticky": "nswe"})]})])
    for name, image in FRAMES.items():
        style.layout(name, [(f"Round.{image}", {"sticky": "nswe"})])
    labels = {f"{name}.TLabel": image for name, (image, _fg) in PILLS.items()}
    for name, image in {**labels, "Badge.TLabel": "badge"}.items():
        style.layout(name, [(f"Round.{image}", {"sticky": "nswe", "children": [
            ("Label.padding", {"sticky": "nswe", "children": [
                ("Label.label", {"sticky": "nswe"})]})]})])


def _buttons(style: ttk.Style, p: Palette, f: Fonts, m: Metrics) -> None:
    """Configura textos, fuentes y márgenes de los botones y sus variantes.

    Args:
        style (ttk.Style): Gestor de estilos.
        p (Palette): Paleta del tema.
        f (Fonts): Fuentes de la app.
        m (Metrics): Escala de la pantalla.
    """
    for name, (_image, fg, font, small) in BUTTONS.items():
        padding = (m.px(9), m.px(4)) if small else (m.px(12), m.px(6))
        style.configure(name, foreground=getattr(p, fg), font=getattr(f, font), padding=padding,
                        anchor="center", focuscolor=p.accent)
        hover_fg = p.text if fg == "muted" else getattr(p, fg)
        style.map(name, foreground=[("disabled", p.muted), ("active", hover_fg)])
        _with_variants(style, name, p)
