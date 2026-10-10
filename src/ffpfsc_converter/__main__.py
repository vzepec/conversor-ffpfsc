"""Punto de entrada: ``python -m ffpfsc_converter [rutas...]``."""
from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Abre la ventana principal y encola las rutas recibidas por argumento.

    Args:
        argv (list[str] | None): Rutas a encolar; ``None`` usa ``sys.argv[1:]``.

    Returns:
        int: Código de salida del proceso (``0`` al cerrar la ventana).
    """
    # Import diferido: permite usar el paquete sin tkinter (tests, scripts).
    from ffpfsc_converter.ui.app import MainWindow

    args = sys.argv[1:] if argv is None else argv
    MainWindow(initial_paths=[Path(a) for a in args]).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
