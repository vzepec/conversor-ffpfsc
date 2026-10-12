"""Ventana modal de la compresión LZ4 en la PS5: juego, destino, opciones y cambios exactos."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ffpfsc_converter.config import DEFAULT_LZ4_PRESET, LZ4_PRESETS
from ffpfsc_converter.domain.lz4 import Lz4Plan, Lz4Request
from ffpfsc_converter.services.lz4_plan import output_name
from ffpfsc_converter.ui.explorer.lz4_presenters import (
    ALREADY_EXISTS,
    LZ4_TITLE,
    compat_info,
    game_text,
    replaces_existing,
    size_text,
    start_blockers,
    warning_lines,
)
from ffpfsc_converter.ui.explorer.lz4_target_presenters import (
    destination_label,
    summary_lines,
    writable_destinations,
)
from ffpfsc_converter.ui.theme import ThemeManager
from ffpfsc_converter.ui.widgets.basics import Segmented
from ffpfsc_converter.ui.widgets.modal import Modal

_PRESETS_BY_LABEL = {p.label: p for p in LZ4_PRESETS}
_KEEP, _REMOVE = "keep", "remove"
_ORIGINAL_OPTIONS = ((_KEEP, "Conservar el original"),
                     (_REMOVE, "Borrar el original al terminar"))
_TEXT_WIDTH = 700
_COLUMN_GAP = 24
_COMPAT_STYLES = {"ok": "CardOk.TLabel", "warn": "CardWarn.TLabel", "bad": "CardBad.TLabel"}


class Lz4Dialog(Modal):
    """Pide destino y opciones de exfat2ampr y muestra qué cambiará en la PS5."""

    def __init__(self, parent: tk.Misc, theme: ThemeManager, plan: Lz4Plan) -> None:
        """Construye la ventana (modal) con el análisis de exfat2ampr.

        Args:
            parent (tk.Misc): Ventana principal.
            theme (ThemeManager): Tema.
            plan (Lz4Plan): Juego, comprobación previa y unidades de la PS5.
        """
        super().__init__(parent, theme, LZ4_TITLE, plan.source.path)
        self.result: Lz4Request | None = None
        self._plan = plan
        self._targets = writable_destinations(plan.destinations)
        bases = [d.base for d in self._targets]
        self._dest = tk.StringVar(value=plan.dest_base if plan.dest_base in bases
                                  else (bases[0] if bases else ""))
        self._preset = tk.StringVar(value=DEFAULT_LZ4_PRESET.label)
        self._original = tk.StringVar(value=_KEEP)
        self._verify, self._overwrite = tk.BooleanVar(value=True), tk.BooleanVar(value=False)
        self._build_game()
        columns = ttk.Frame(self.body, style="Surface.TFrame")
        columns.pack(fill="x")
        left = ttk.Frame(columns, style="Surface.TFrame")
        left.pack(side="left", fill="y", anchor="n", padx=(0, theme.metrics.px(_COLUMN_GAP)))
        right = ttk.Frame(columns, style="Surface.TFrame")
        right.pack(side="left", fill="both", expand=True, anchor="n")
        self._build_destinations(left)
        self._build_options(right)
        self._build_summary()
        self._start = self.add_button("Comprimir en la PS5", self._accept, "Card.Accent.TButton")
        self.add_button("Cancelar", self._cancel)
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.show_modal()

    def ask(self) -> Lz4Request | None:
        """Muestra la ventana y espera hasta que se cierre.

        Returns:
            Lz4Request | None: Conversión elegida, o ``None`` si se canceló.
        """
        self.wait_window()
        return self.result

    def _build_game(self) -> None:
        """Muestra el juego, su compatibilidad y el espacio que necesita."""
        m, check = self.theme.metrics, self._plan.check
        compat = compat_info(check.compatible)
        ttk.Label(self.body, text=game_text(self._plan.source),
                  style="CardBold.TLabel").pack(anchor="w")
        ttk.Label(self.body, text=compat.text, style=_COMPAT_STYLES[compat.kind],
                  justify="left", wraplength=m.px(_TEXT_WIDTH)).pack(anchor="w",
                                                                     pady=(m.px(6), 0))
        ttk.Label(self.body, text=size_text(check), style="CardMuted.TLabel").pack(
            anchor="w", pady=(m.px(4), 0))

    def _caption(self, parent: tk.Misc, text: str) -> None:
        """Agrega el título de una sección.

        Args:
            parent (tk.Misc): Columna donde va la sección.
            text (str): Título en mayúsculas.
        """
        m = self.theme.metrics
        ttk.Label(parent, text=text, style="CardCaption.TLabel").pack(
            anchor="w", pady=(m.px(14), m.px(4)))

    def _build_destinations(self, parent: tk.Misc) -> None:
        """Lista las unidades escribibles con su espacio libre (una por línea).

        Args:
            parent (tk.Misc): Columna izquierda.
        """
        self._caption(parent, "DESTINO")
        if not self._targets:
            ttk.Label(parent, text="No hay ninguna unidad donde guardar.",
                      style="CardBad.TLabel").pack(anchor="w")
            return
        box = ttk.Frame(parent, style="Card.SegBox.TFrame", padding=3)
        box.pack(fill="x")
        for dest in self._targets:
            ttk.Radiobutton(box, text=destination_label(dest), value=dest.base,
                            variable=self._dest, style="Seg.Toolbutton", takefocus=False,
                            command=self._refresh).pack(fill="x")

    def _build_options(self, body: tk.Misc) -> None:
        """Crea el modo LZ4, la verificación, el reemplazo y qué hacer con el original.

        Args:
            body (tk.Misc): Columna derecha.
        """
        m = self.theme.metrics
        self._caption(body, "MODO")
        Segmented(body, self._preset, [(p.label, p.short_label) for p in LZ4_PRESETS],
                  self._refresh).pack(anchor="w")
        self._mode = ttk.Label(body, style="CardMuted.TLabel")
        self._mode.pack(anchor="w", pady=(m.px(4), 0))
        switch = self.theme.switch_style("surface")
        switches = [("  Verificar al terminar (más lento)", self._verify)]
        plan = self._plan
        if ALREADY_EXISTS in plan.check.warnings and not output_name(plan.source, plan.dest_base):
            switches.append(("  Reemplazar el comprimido anterior", self._overwrite))
        for text, variable in switches:
            ttk.Checkbutton(body, text=text, variable=variable, style=switch,
                            command=self._refresh).pack(anchor="w", pady=(m.px(10), 0))
        self._caption(body, "ORIGINAL")
        Segmented(body, self._original, _ORIGINAL_OPTIONS, self._refresh).pack(anchor="w")

    def _build_summary(self) -> None:
        """Crea los avisos, los errores y el recuadro con las rutas exactas."""
        m, width = self.theme.metrics, self.theme.metrics.px(_TEXT_WIDTH)
        warnings = warning_lines(self._plan.check)
        if warnings:
            ttk.Label(self.body, text="\n".join(f"• {w}" for w in warnings),
                      style="CardWarn.TLabel", justify="left", wraplength=width).pack(
                anchor="w", pady=(m.px(14), 0))
        self._errors = ttk.Label(self.body, style="CardBad.TLabel", justify="left",
                                 wraplength=width)
        box = ttk.Frame(self.body, style="Card.Bar.TFrame", padding=(m.px(12), m.px(10)))
        box.pack(fill="x", pady=(m.px(14), 0))
        self._summary = ttk.Label(box, style="AltWarn.TLabel", justify="left",
                                  wraplength=width - m.px(24))
        self._summary.pack(anchor="w")
        self._box = box

    def _request(self) -> Lz4Request | None:
        """Arma la conversión con las opciones elegidas.

        Returns:
            Lz4Request | None: Conversión, o ``None`` si no hay destino escribible.
        """
        if not self._dest.get():
            return None
        source, dest = self._plan.source, self._dest.get()
        return Lz4Request(
            source=source, dest_base=dest,
            level=_PRESETS_BY_LABEL[self._preset.get()].level, verify=self._verify.get(),
            remove_source=self._original.get() == _REMOVE, overwrite=self._overwrite.get(),
            name=output_name(source, dest))

    def _refresh(self) -> None:
        """Actualiza el modo, los errores que aplican, el resumen y el botón de inicio."""
        self._mode.configure(text=self._preset.get())
        request = self._request()
        check, checked = self._plan.check, self._plan.dest_base
        errors = start_blockers(check, checked, request) if request is not None else []
        self._errors.configure(text="\n".join(f"• {e}" for e in errors))
        if errors:
            self._errors.pack(anchor="w", pady=(self.theme.metrics.px(10), 0), before=self._box)
        else:
            self._errors.pack_forget()
        lines = (summary_lines(request, replaces_existing(check, checked, request))
                 if request is not None else [])
        self._summary.configure(text="\n".join(lines) or "No hay dónde guardar el juego.")
        can_start = request is not None and not errors
        self._start.state(["!disabled"] if can_start else ["disabled"])

    def _accept(self) -> None:
        """Guarda la conversión elegida y cierra la ventana."""
        self.result = self._request()
        self.destroy()

    def _cancel(self) -> None:
        """Cierra la ventana sin elegir."""
        self.result = None
        self.destroy()
