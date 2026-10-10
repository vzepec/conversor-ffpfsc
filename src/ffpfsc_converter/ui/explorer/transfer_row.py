"""Fila de una transferencia: nombre, avance o estado, velocidad y tiempo restante."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.ui.explorer.transfer_presenters import TransferProgress
from ffpfsc_converter.ui.theme import ThemeManager

_PILLS = {"wait": "PillWait", "run": "PillRun", "ok": "PillOk", "warn": "PillWarn",
          "bad": "PillBad"}
_SPEED_W, _ETA_W = 92, 120


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
            icon (str): ``"download"`` o ``"upload"``.
        """
        m = theme.metrics
        super().__init__(parent, style="Surface.TFrame")
        body = ttk.Frame(self, style="Surface.TFrame", padding=(m.px(14), m.px(9)))
        body.pack(fill="x")
        ttk.Separator(self).pack(fill="x")
        for column, weight in ((0, 13), (1, 14)):
            body.columnconfigure(column, weight=weight, uniform="transfer")
        body.columnconfigure(2, minsize=m.px(_SPEED_W))
        body.columnconfigure(3, minsize=m.px(_ETA_W))
        ttk.Label(body, text=f" {name}", image=theme.icons.get(icon, 16, "muted"),
                  compound="left", style="Card.TLabel").grid(row=0, column=0, rowspan=2,
                                                             sticky="w", padx=(0, m.px(14)))
        self._label = ttk.Label(body, style="CardSmall.TLabel")
        self._label.grid(row=0, column=1, sticky="w")
        self._bar = ttk.Progressbar(body, maximum=100, style="Thin.Horizontal.TProgressbar")
        self._pill = ttk.Label(body)
        self._detail = ttk.Label(body, style="CardSmall.TLabel")
        self._speed = ttk.Label(body, style="CardSmall.TLabel", anchor="e")
        self._speed.grid(row=0, column=2, rowspan=2, sticky="e")
        self._eta = ttk.Label(body, style="CardSmall.TLabel", anchor="e")
        self._eta.grid(row=0, column=3, rowspan=2, sticky="e")
        self._bar_pad = m.px(5)
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
