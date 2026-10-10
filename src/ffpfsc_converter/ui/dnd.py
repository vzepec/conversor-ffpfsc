"""Soporte opcional de arrastrar y soltar (tkinterdnd2).

Si ``tkinterdnd2`` no está instalado la aplicación funciona igual, solo que
sin arrastrar y soltar.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path

from ffpfsc_converter.ui.presenters import parse_dropped_item

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except Exception:  # noqa: BLE001 - cualquier fallo de carga desactiva DnD
    HAS_DND = False


def create_root() -> tk.Tk:
    """Crea la ventana raíz, con soporte DnD si está disponible."""
    return TkinterDnD.Tk() if HAS_DND else tk.Tk()


def register_drop_target(widget: tk.Misc, on_paths: Callable[[list[Path]], None]) -> None:
    """Hace que ``widget`` acepte archivos/carpetas soltados."""
    if not HAS_DND:
        return

    def handle(event: tk.Event) -> None:
        items = widget.tk.splitlist(event.data)
        on_paths([parse_dropped_item(item) for item in items])

    widget.drop_target_register(DND_FILES)
    widget.dnd_bind("<<Drop>>", handle)
