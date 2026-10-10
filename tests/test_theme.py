from __future__ import annotations

from ffpfsc_converter.ui.theme import DARK, LIGHT, TILE_COLORS, resolve_palette
from ffpfsc_converter.ui.theme.app_icon import WINDOW_ICON_SIZES, render_app_icon
from ffpfsc_converter.ui.theme.fonts import pick_family
from ffpfsc_converter.ui.theme.icon_shapes import SHAPES
from ffpfsc_converter.ui.theme.icons import render_icon, render_switch
from ffpfsc_converter.ui.theme.metrics import Metrics
from ffpfsc_converter.ui.theme.rounded import SPECS
from ffpfsc_converter.ui.theme.shapes import (
    RoundSpec,
    render_circle,
    render_dashed_card,
    render_rounded,
)
from ffpfsc_converter.ui.widgets.basics import initials, tile_color


def test_resolve_palette() -> None:
    """Respeta el modo elegido y, en «sistema», usa oscuro si no se conoce la preferencia."""
    assert resolve_palette("light", True) is LIGHT
    assert resolve_palette("dark", False) is DARK
    assert resolve_palette("system", False) is LIGHT
    assert resolve_palette("system", True) is DARK
    assert resolve_palette("system", None) is DARK


def test_palettes_are_complete() -> None:
    """Ambas paletas indican si son oscuras y usan colores #rrggbb."""
    assert DARK.is_dark and not LIGHT.is_dark
    for palette in (DARK, LIGHT):
        colors = [v for k, v in vars(palette).items() if k != "name"]
        assert all(c.startswith("#") and len(c) == 7 for c in colors)


def test_pick_family() -> None:
    """Elige la primera fuente instalada sin distinguir mayúsculas."""
    assert pick_family(["Segoe UI", "Noto Sans"], ["noto sans", "Arial"], "TkDefault") == \
        "noto sans"
    assert pick_family(["Segoe UI"], ["Arial"], "TkDefault") == "TkDefault"


def test_metrics_scale_is_clamped() -> None:
    """Escala las medidas y limita el factor entre 1 y 3."""
    assert Metrics(1.5).px(10) == 15
    assert Metrics(0.5).px(10) == 10
    assert Metrics(9).px(10) == 30


def test_initials_and_tile_color() -> None:
    """Toma hasta dos iniciales y da siempre el mismo color al mismo juego."""
    assert initials("Silent Hill f") == "SH"
    assert initials("astro-bot") == "AB"
    assert initials("") == "?"
    assert tile_color("Juego") == tile_color("Juego")
    assert tile_color("Juego") in TILE_COLORS


def test_icons_render_at_requested_size() -> None:
    """Dibuja todos los iconos y el interruptor con el tamaño pedido."""
    for name in SHAPES:
        assert render_icon(name, 16, "#ffffff").size == (16, 16)
    assert render_switch(True, 34, 20, DARK).size == (34, 20)


def test_render_rounded_has_transparent_corners() -> None:
    """Dibuja el relleno con las esquinas transparentes y respeta el tamaño pedido."""
    image = render_rounded((40, 20), 8, "#ff0000", "#00ff00")
    assert image.size == (40, 20)
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((20, 10))[:3] == (255, 0, 0)
    assert render_rounded((10, 10), 3, None, None).getpixel((5, 5))[3] == 0


def test_round_specs_can_be_sliced() -> None:
    """Cada imagen deja una zona central estirable y usa colores de la paleta."""
    assert RoundSpec(12, 96, 3, "line", inset=2).border == 5
    for spec in SPECS.values():
        assert min(spec.width, spec.height) >= 2 * spec.border + 1
        for attr in (spec.fill, spec.outline):
            assert attr is None or hasattr(DARK, attr)


def test_render_circle_is_antialiased() -> None:
    """Suaviza el borde del círculo y suma el halo al tamaño de la imagen."""
    image = render_circle(20, "#ff0000")
    assert image.size == (20, 20)
    assert image.getpixel((0, 0))[3] == 0
    low, high = image.getchannel("A").getextrema()
    alphas = image.getchannel("A").histogram()
    assert (low, high) == (0, 255) and any(alphas[1:255])  # borde con transparencia parcial
    assert image.getpixel((10, 10)) == (255, 0, 0, 255)
    assert render_circle(20, "#ff0000", halo=(4, "#00ff00")).size == (28, 28)


def test_dashed_card_alternates_dashes_and_gaps() -> None:
    """El borde punteado deja huecos y las esquinas quedan transparentes."""
    image = render_dashed_card((200, 60), 12, "#000000", ("#ffffff", 1.5), (6, 4))
    assert image.size == (200, 60)
    assert image.getpixel((0, 0))[3] == 0
    top_edge = [image.getpixel((x, 0))[:3] for x in range(20, 180)]
    assert (255, 255, 255) in top_edge and any(c[0] < 128 for c in top_edge)


def test_app_icon_sizes() -> None:
    """Dibuja el icono a cada tamaño con las esquinas transparentes."""
    for size in WINDOW_ICON_SIZES:
        icon = render_app_icon(size)
        assert icon.size == (size, size) and icon.getpixel((0, 0))[3] < 8  # resto del suavizado
