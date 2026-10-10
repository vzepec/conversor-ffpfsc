"""Integración con el escritorio del sistema operativo."""
from __future__ import annotations

import subprocess
from pathlib import Path


def open_in_file_manager(path: Path) -> None:
    """Abre ``path`` con el gestor de archivos predeterminado (xdg-open)."""
    subprocess.Popen(
        ["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
