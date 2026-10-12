"""Fila de una transferencia: nombre, avance o estado, velocidad y tiempo restante."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ffpfsc_converter.ui.explorer.transfer_presenters import TransferProgress
from ffpfsc_converter.ui.theme import ThemeManager

_PILLS = {"wait": "PillWait", "run": "PillRun", "ok": "PillOk", "warn": "PillWarn",
          "bad": "PillBad"}
_SPEED_W, _ETA_W, _DETAIL_W = 92, 120, 380
#: Peso de las columnas del nombre y del estado (comparten el ancho sobrante).
_NAME_WEIGHT, _STATUS_WEIGHT = 13, 14
_PAD_X, _MIN_DETAIL_W = 14, 120


class TransferRow(ttk.Frame):
    """Una descarga o subida en el panel de transferencias.

    Attributes:
        is_active (bool): ``True`` mientras está en cola o en curso.
    """

    def __init__(self, parent: tk.Misc, theme: ThemeManager, name: str, icon: str) -> None:
        """Crea la fila en estado «En cola».

        Args:
            parent (tk.Misc): Contenedor.
            theme (ThemeManager): Tema.
            name (str): Archivo o carpeta.
            icon (str): ``"download"``, ``"upload"`` o ``"replace"``.
        """
        m = self._m = theme.metrics
        self._theme = theme
        super().__init__(parent, style="Surface.TFrame")
        body = ttk.Frame(self, style="Surface.TFrame", padding=(m.px(_PAD_X), m.px(9)))
        body.pack(fill="x")
        ttk.Separator(self).pack(fill="x")
        for column, weight in ((0, _NAME_WEIGHT), (1, _STATUS_WEIGHT)):
            body.columnconfigure(column, weight=weight, uniform="transfer")
        body.columnconfigure(2, minsize=m.px(_SPEED_W))
        body.columnconfigure(3, minsize=m.px(_ETA_W))
        self._body = body
        self._name = ttk.Label(body, text=f" {name}", image=theme.icons.get(icon, 16, "muted"),
                               compound="left", style="Card.TLabel")
        self._name.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, m.px(_PAD_X)))
        self._subtitle = ttk.Label(body, style="CardSmall.TLabel")
        self._action: ttk.Button | None = None
        self._secondary: ttk.Button | None = None
        self._label = ttk.Label(body, style="CardSmall.TLabel")
        self._label.grid(row=0, column=1, sticky="w")
        self._bar = ttk.Progressbar(body, maximum=100, style="Thin.Horizontal.TProgressbar")
        self._pill = ttk.Label(body)
        self._detail = ttk.Label(body, style="CardSmall.TLabel", wraplength=m.px(_DETAIL_W))
        self._speed = ttk.Label(body, style="CardSmall.TLabel", anchor="e")
        self._speed.grid(row=0, column=2, rowspan=2, sticky="e")
        self._eta = ttk.Label(body, style="CardSmall.TLabel", anchor="e")
        self._eta.grid(row=0, column=3, rowspan=2, sticky="e")
        self._bar_pad = m.px(5)
        body.bind("<Configure>", lambda _e: self._fit_detail(), add="+")
        self.is_active = True
        self.set_state("wait", "En cola")

    def set_progress(self, progress: TransferProgress, speed: str, eta: str) -> None:
        """Muestra el porcentaje, la barra, la velocidad y el tiempo restante.

        Args:
            progress (TransferProgress): Avance.
            speed (str): Velocidad ya formateada.
            eta (str): Tiempo restante ya formateado.
        """
        self.is_active = True
        self._pill.grid_remove()
        self._detail.grid_remove()
        self._label.configure(text=progress.text)
        self._label.grid()
        self._bar.configure(value=progress.percent)
        self._bar.grid(row=1, column=1, sticky="ew", pady=(self._bar_pad, 0))
        self._speed.configure(text=speed or "—")
        self._eta.configure(text=eta or "—")

    def set_state(self, kind: str, label: str, detail: str = "",
                  active: bool | None = None) -> None:
        """Muestra una píldora de estado (en cola, reintentando, terminado o error).

        Args:
            kind (str): ``"wait"``, ``"run"``, ``"ok"``, ``"warn"`` o ``"bad"``.
            label (str): Texto de la píldora.
            detail (str): Motivo o resultado.
            active (bool | None): Si sigue en curso; ``None`` = según el tipo de píldora.
        """
        self.is_active = kind in ("wait", "run") if active is None else active
        self._label.grid_remove()
        self._bar.grid_remove()
        self._pill.configure(text=label, style=f"Card.{_PILLS.get(kind, 'PillWait')}.TLabel")
        self._pill.grid(row=0, column=1, sticky="w")
        self._detail.configure(text=detail)
        if detail:
            self._detail.grid(row=1, column=1, sticky="w", pady=(self._bar_pad, 0))
        else:
            self._detail.grid_remove()
        self._speed.configure(text="—")
        self._eta.configure(text="—")

    def _fit_detail(self) -> None:
        """Ajusta el ancho del detalle a su columna para que el texto no quede cortado.

        Se calcula con el ancho de la fila (no con el de la columna) porque un detalle
        más ancho que la columna la ensancharía y empujaría la velocidad fuera de la fila.
        """
        m = self._m
        free = (self._body.winfo_width() - m.px(3 * _PAD_X) - m.px(_SPEED_W) - m.px(_ETA_W))
        share = free * _STATUS_WEIGHT // (_NAME_WEIGHT + _STATUS_WEIGHT)
        width = min(max(share, m.px(_MIN_DETAIL_W)), m.px(_DETAIL_W))
        if width != int(self._detail.cget("wraplength")):
            self._detail.configure(wraplength=width)

    def set_subtitle(self, text: str) -> None:
        """Muestra una línea bajo el nombre (por ejemplo, el paso del reemplazo).

        Args:
            text (str): Texto de la línea; vacío la oculta.
        """
        self._subtitle.configure(text=text)
        if text:
            self._name.grid(row=0, column=0, rowspan=1, sticky="sw")
            self._subtitle.grid(row=1, column=0, sticky="nw", padx=(self._m.px(22), 0),
                                pady=(self._m.px(3), 0))
        else:
            self._subtitle.grid_remove()
            self._name.grid(row=0, column=0, rowspan=2, sticky="w")

    def set_action(self, text: str, command: Callable[[], None], style: str) -> None:
        """Muestra un botón en la fila (Cancelar o Reintentar); texto vacío lo oculta.

        Args:
            text (str): Texto del botón.
            command (Callable[[], None]): Acción.
            style (str): Estilo ttk (por ejemplo ``"Card.SmallDanger.TButton"``).
        """
        if not text:
            if self._action is not None:
                self._action.grid_remove()
            self._eta.grid(row=0, column=3, rowspan=2, sticky="e")
            return
        if self._action is None:
            self._action = ttk.Button(self._body, takefocus=False)
        self._action.configure(text=text, command=command, style=style)
        self._action.state(["!disabled"])
        self._eta.grid(row=0, column=3, rowspan=1, sticky="se")
        self._action.grid(row=1, column=3, sticky="ne", pady=(self._m.px(4), 0))

    def set_secondary(self, text: str, command: Callable[[], None]) -> None:
        """Muestra un segundo botón (por ejemplo «Saltar verificación»); texto vacío lo oculta.

        Va bajo la velocidad, a la izquierda del botón principal.

        Args:
            text (str): Texto del botón.
            command (Callable[[], None]): Acción.
        """
        if not text:
            if self._secondary is not None:
                self._secondary.grid_remove()
            self._speed.grid(row=0, column=2, rowspan=2, sticky="e")
            return
        if self._secondary is None:
            self._secondary = ttk.Button(self._body, takefocus=False, style="Card.Small.TButton")
        self._secondary.configure(text=text, command=command)
        self._speed.grid(row=0, column=2, rowspan=1, sticky="se")
        self._secondary.grid(row=1, column=2, sticky="ne", pady=(self._m.px(4), 0),
                             padx=(0, self._m.px(8)))

    def disable_action(self, text: str) -> None:
        """Deshabilita el botón de la fila mientras se atiende (por ejemplo, «Cancelando…»).

        Args:
            text (str): Texto a mostrar en el botón.
        """
        if self._action is not None:
            self._action.configure(text=text)
            self._action.state(["disabled"])
