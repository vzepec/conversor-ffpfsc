"""Ajustes del usuario guardados en un archivo JSON.

Ubicación: ``%APPDATA%\\ffpfsc-converter`` en Windows y
``$XDG_CONFIG_HOME/ffpfsc-converter`` (o ``~/.config/ffpfsc-converter``) en
Linux y macOS.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_APP_DIR = "ffpfsc-converter"
_FILE_NAME = "settings.json"


def settings_path(
    platform: str = sys.platform,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Calcula la ruta del archivo de ajustes según el sistema operativo.

    Args:
        platform (str): Valor de ``sys.platform`` del sistema destino.
        env (Mapping[str, str] | None): Variables de entorno; ``None`` usa ``os.environ``.
        home (Path | None): Carpeta personal; ``None`` usa ``Path.home()``.

    Returns:
        Path: Ruta de ``settings.json``.
    """
    env = os.environ if env is None else env
    home = home or Path.home()
    if platform == "win32" and env.get("APPDATA"):
        base = Path(env["APPDATA"])
    elif env.get("XDG_CONFIG_HOME"):
        base = Path(env["XDG_CONFIG_HOME"])
    else:
        base = home / ".config"
    return base / _APP_DIR / _FILE_NAME


def load_settings(path: Path | None = None) -> dict[str, Any]:
    """Lee los ajustes guardados.

    Args:
        path (Path | None): Archivo a leer; ``None`` usa ``settings_path()``.

    Returns:
        dict[str, Any]: Ajustes guardados, o un diccionario vacío si el archivo
        no existe o está dañado.
    """
    path = path or settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(values: Mapping[str, Any], path: Path | None = None) -> None:
    """Guarda los ajustes, fusionándolos con los existentes.

    Los fallos de escritura se ignoran: perder un ajuste nunca debe impedir
    usar la aplicación.

    Args:
        values (Mapping[str, Any]): Ajustes a guardar (serializables en JSON).
        path (Path | None): Archivo a escribir; ``None`` usa ``settings_path()``.
    """
    path = path or settings_path()
    merged = {**load_settings(path), **values}
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
