"""Integración con el escritorio del sistema operativo."""
from __future__ import annotations

import subprocess
from pathlib import Path


def open_in_file_manager(path: Path) -> None:
    """Abre una carpeta con el gestor de archivos predeterminado (``xdg-open``).

    Args:
        path (Path): Carpeta a abrir.

    Raises:
        OSError: Si ``xdg-open`` no está disponible.
    """
    subprocess.Popen(
        ["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
