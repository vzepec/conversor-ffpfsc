"""Genera los archivos del icono de la app para los accesos directos.

Crea ``assets/icon.png`` (Linux, archivo ``.desktop``) y ``assets/icon.ico``
(Windows, accesos directos ``.lnk``) a partir del mismo dibujo que usa la ventana.

Uso: ``python tools/make_icon.py`` (vuelve a generarlos si cambia el diseño).
"""
from __future__ import annotations

import sys
from pathlib import Path

from ffpfsc_converter.ui.theme.app_icon import WINDOW_ICON_SIZES, render_app_icon

PNG_SIZE = 256
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def make_icons(out_dir: Path) -> tuple[Path, Path]:
    """Dibuja el icono y lo guarda como PNG y como ICO con varios tamaños.

    Args:
        out_dir (Path): Carpeta de destino (se crea si no existe).

    Returns:
        tuple[Path, Path]: Rutas del ``.png`` y del ``.ico`` generados.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    png, ico = out_dir / "icon.png", out_dir / "icon.ico"
    render_app_icon(PNG_SIZE).save(png)
    render_app_icon(max(WINDOW_ICON_SIZES)).save(
        ico, sizes=[(size, size) for size in WINDOW_ICON_SIZES])
    return png, ico


def main() -> int:
    """Genera los iconos en ``assets/``.

    Returns:
        int: Código de salida (``0``).
    """
    for path in make_icons(ASSETS_DIR):
        print(f"Generado: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
