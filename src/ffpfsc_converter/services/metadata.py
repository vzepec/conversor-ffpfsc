"""Lectura del nombre oficial, Title ID y versión del juego."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ffpfsc_converter.config import PARAM_JSON_MAX_BYTES, PARAM_JSON_RELPATH, PREFERRED_LANGUAGES
from ffpfsc_converter.domain.models import GameInfo
from ffpfsc_converter.infrastructure import mkpfs_adapter

_FALLBACK_TITLE_KEYS = ("titleName", "title", "name")


def parse_param_json(data: bytes) -> GameInfo:
    """Extrae los metadatos de un ``param.json`` de PS5.

    Args:
        data (bytes): Contenido del archivo, con o sin BOM UTF-8.

    Returns:
        GameInfo: Metadatos leídos; vacío si el JSON no es un objeto.

    Raises:
        json.JSONDecodeError: Si el contenido no es JSON válido.
        UnicodeDecodeError: Si el contenido no es UTF-8.
    """
    root = json.loads(data.decode("utf-8-sig"))
    if not isinstance(root, dict):
        return GameInfo()
    return GameInfo(
        title=_pick_title(root),
        title_id=str(root.get("titleId") or ""),
        version=str(root.get("contentVersion") or root.get("masterVersion") or ""),
    )


def _pick_title(root: dict[str, Any]) -> str:
    """Elige el nombre del juego según la prioridad de idiomas.

    Orden: idioma predeterminado del juego, ``en-US``, español
    (``PREFERRED_LANGUAGES``), cualquier otro idioma y, por último, las claves
    de primer nivel.

    Args:
        root (dict[str, Any]): Objeto raíz de ``param.json``.

    Returns:
        str: Nombre encontrado sin espacios extremos, o cadena vacía.
    """
    localized = root.get("localizedParameters")
    if isinstance(localized, dict):
        order = [str(localized.get("defaultLanguage") or "en-US"), "en-US", *PREFERRED_LANGUAGES]
        order += [lang for lang in localized if lang not in order]
        for lang in order:
            params = localized.get(lang)
            if isinstance(params, dict):
                name = str(params.get("titleName") or "").strip()
                if name:
                    return name
    for key in _FALLBACK_TITLE_KEYS:
        value = root.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def read_game_info(target: Path) -> GameInfo:
    """Lee los metadatos desde una carpeta de juego o una imagen.

    Es *best effort*: ante cualquier problema devuelve un ``GameInfo`` vacío,
    porque el nombre es informativo y nunca debe bloquear la conversión.

    Args:
        target (Path): Carpeta con ``eboot.bin`` o imagen ``.exfat``/``.ffpkg``.

    Returns:
        GameInfo: Metadatos leídos, o vacío si no se pudieron obtener.
    """
    try:
        if target.is_dir():
            param = target / PARAM_JSON_RELPATH
            if param.is_file():
                return parse_param_json(param.read_bytes())
        elif target.suffix.lower() == ".exfat":
            data = mkpfs_adapter.read_exfat_member(target, PARAM_JSON_RELPATH, PARAM_JSON_MAX_BYTES)
            if data is not None:
                return parse_param_json(data)
        return mkpfs_adapter.read_metadata(target)
    except Exception:  # noqa: BLE001 - ver docstring
        return GameInfo()
