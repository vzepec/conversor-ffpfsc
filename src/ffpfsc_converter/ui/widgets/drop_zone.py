"""Zona para soltar juegos: tarjeta con borde punteado, icono, textos y botones."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from pathlib import Path
from tkinter import ttk

from ffpfsc_converter.ui.dnd import register_drop_target
from ffpfsc_converter.ui.theme import Palette, ThemeManager

_HEIGHT = 92
_RADIUS = 12


class DropZone(tk.Canvas):
    """Recibe carpetas o imágenes soltadas y ofrece botones para elegirlas."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, title: str, subtitle: str,
                 buttons: Sequence[tuple[str, Callable[[], None]]],
                 on_paths: Callable[[list[Path]], None]) -> None:
        """Crea la zona.

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            title (str): Texto principal.
            subtitle (str): Texto de ayuda.
            buttons (Sequence[tuple[str, Callable[[], None]]]): Botones (texto, acción).
            on_paths (Callable[[list[Path]], None]): Recibe las rutas soltadas.
        """
        self._theme = theme
        m = theme.metrics
        super().__init__(parent, height=m.px(_HEIGHT), highlightthickness=0, bd=0,
                         background=theme.palette.bg)
        body = ttk.Frame(self, style="Surface.TFrame")
        badge = ttk.Label(body, image=theme.icons.get("drop", 22, "accent"),
                          style="Card.Badge.TLabel")
        badge.pack(side="left")
        # Los botones se empaquetan antes que los textos para que nunca queden recortados.
        for text, command in reversed(buttons):
            ttk.Button(body, text=text, command=command, style="Card.TButton").pack(
                side="right", padx=(m.px(6), 0))
        texts = ttk.Frame(body, style="Surface.TFrame")
        texts.pack(side="left", padx=m.px(14))
        ttk.Label(texts, text=title, style="CardHeading.TLabel").pack(anchor="w")
        ttk.Label(texts, text=subtitle, style="CardMuted.TLabel").pack(anchor="w")
        self._body = self.create_window(0, 0, window=body, anchor="nw")
        self._frame_body = body
        self.bind("<Configure>", lambda _e: self._draw())
        theme.on_change(lambda _p: self._draw())
        for widget in (self, body, texts, badge, *texts.winfo_children()):
            register_drop_target(widget, on_paths)
            if buttons:  # clic en cualquier parte = primer botón (elegir carpeta)
                widget.bind("<Button-1>", lambda _e: buttons[0][1]())
                widget.configure(cursor="hand2")

    def _draw(self) -> None:
        """Dibuja el fondo y el borde punteado al tamaño actual."""
        p: Palette = self._theme.palette
        m = self._theme.metrics
        w, h = self.winfo_width(), self.winfo_height()
        self.configure(background=p.bg)
        self.delete("frame")
        r = m.px(_RADIUS)
        self._rounded(2, 2, w - 2, h - 2, r, fill=p.surface, outline=p.line, dash=(5, 4))
        pad = m.px(16)
        self.coords(self._body, pad, (h - self._frame_body.winfo_reqheight()) // 2)
        self.itemconfigure(self._body, width=max(1, w - 2 * pad))
        self.tag_raise(self._body)

    def _rounded(self, x0: int, y0: int, x1: int, y1: int, r: int, **opts: object) -> None:
        """Dibuja un rectángulo de esquinas redondeadas (polígono suavizado).

        Args:
            x0 (int): Borde izquierdo.
            y0 (int): Borde superior.
            x1 (int): Borde derecho.
            y1 (int): Borde inferior.
            r (int): Radio de las esquinas.
            **opts (object): Opciones del polígono (relleno, borde, punteado).
        """
        points = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
                  x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        self.create_polygon(points, smooth=True, tags="frame", width=1.5, **opts)
