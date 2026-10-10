"""Paletas de color de la interfaz (clara y oscura).

Un único color de acento (azul cobalto). Verde, ámbar y rojo se reservan para
estados: listo, aviso y error.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """Colores de un tema.

    Attributes:
        name (str): ``"dark"`` o ``"light"``.
        bg (str): Fondo de las vistas.
        side (str): Fondo de la barra lateral.
        surface (str): Fondo de tarjetas, listas y campos.
        surface2 (str): Fondo secundario (pistas de barras, segmentos inactivos).
        line (str): Bordes y separadores.
        text (str): Texto principal.
        muted (str): Texto secundario.
        accent (str): Color de acento (acciones principales, progreso).
        accent_hover (str): Acento al pasar el puntero.
        accent_ink (str): Texto sobre el acento.
        accent_soft (str): Fondo suave del acento (selección, navegación activa).
        ok (str): Estado listo.
        ok_soft (str): Fondo del estado listo.
        warn (str): Estado de aviso.
        warn_soft (str): Fondo del estado de aviso.
        bad (str): Estado de error y acciones destructivas.
        bad_soft (str): Fondo del estado de error.
        log_bg (str): Fondo del registro técnico.
        log_fg (str): Texto del registro técnico.
    """

    name: str
    bg: str
    side: str
    surface: str
    surface2: str
    line: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    accent_ink: str
    accent_soft: str
    ok: str
    ok_soft: str
    warn: str
    warn_soft: str
    bad: str
    bad_soft: str
    log_bg: str
    log_fg: str

    @property
    def is_dark(self) -> bool:
        """Indica si es el tema oscuro.

        Returns:
            bool: ``True`` para la paleta oscura.
        """
        return self.name == "dark"


DARK = Palette(
    name="dark", bg="#0e1320", side="#0a0f1a", surface="#151c2c", surface2="#1b2437",
    line="#26314a", text="#e6ebf5", muted="#8b97ae", accent="#4c8dff", accent_hover="#6a9fff",
    accent_ink="#ffffff", accent_soft="#17284a", ok="#3ccf91", ok_soft="#12372a",
    warn="#f2b84b", warn_soft="#3a2d12", bad="#ff6b6b", bad_soft="#3d1a1d",
    log_bg="#0a0f1a", log_fg="#b8c2d6",
)

LIGHT = Palette(
    name="light", bg="#f3f5f9", side="#e8ecf4", surface="#ffffff", surface2="#eef2f8",
    line="#d8dfeb", text="#141b2b", muted="#5d6a82", accent="#2f6fe8", accent_hover="#255fd0",
    accent_ink="#ffffff", accent_soft="#e2ebfd", ok="#1f9d6a", ok_soft="#dff5ea",
    warn="#a86a12", warn_soft="#fcf0d9", bad="#d64545", bad_soft="#fde5e5",
    log_bg="#eef2f8", log_fg="#3a4660",
)

#: Colores de las fichas con iniciales de cada juego (legibles en ambos temas).
TILE_COLORS = ("#6d4ae0", "#1f8bd6", "#d9613a", "#0f9d8a", "#c2418f", "#7a8b16", "#b5562b")
