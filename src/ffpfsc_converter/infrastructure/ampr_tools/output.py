"""Interpretación de la salida de ``ampr_pack.py``: avance y resumen JSON final."""
from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from ffpfsc_converter.domain.models import ProgressUpdate

#: ``[pack  10%] packing: files 0/13, 0 B/12.5 MiB, elapsed 00:00:00``
_PROGRESS = re.compile(r"^\[pack\s+(\d{1,3})%\]\s+([\w-]+):")
#: En la fase ``packing``, ``files H/N``: N es la cantidad de archivos que se empaquetan.
_PACKING_TOTAL = re.compile(r"\]\s+packing:\s+files\s+\d+/(\d+)")


@dataclass(frozen=True)
class PackSummary:
    """Resumen que imprime ``ampr_pack.py pack`` al terminar.

    Attributes:
        loose_paths (tuple[str, ...]): Archivos que quedan sin empaquetar (se copian tal cual).
        files_packed (int): Archivos dentro de los paquetes.
        logical_bytes (int): Bytes originales de los archivos empaquetados.
        stored_bytes (int): Bytes que ocupan en los paquetes.
    """

    loose_paths: tuple[str, ...]
    files_packed: int
    logical_bytes: int
    stored_bytes: int


def parse_pack_progress(line: str) -> ProgressUpdate | None:
    """Reconoce una línea de avance de ``ampr_pack.py``.

    Args:
        line (str): Línea de la salida.

    Returns:
        ProgressUpdate | None: Porcentaje total y etapa (``packing``, ``finalizing``…),
        o ``None`` si la línea no es de avance.
    """
    match = _PROGRESS.match(line.strip())
    if match is None:
        return None
    return ProgressUpdate(min(int(match.group(1)), 100), match.group(2))


def packed_file_total(line: str) -> int | None:
    """Lee cuántos archivos va a empaquetar ``ampr_pack.py`` (fase ``packing``).

    Args:
        line (str): Línea de la salida.

    Returns:
        int | None: Cantidad de archivos, o ``None`` si la línea no la indica.
    """
    match = _PACKING_TOTAL.search(line)
    return int(match.group(1)) if match else None


def json_tail(lines: Sequence[str]) -> str:
    """Extrae el último objeto JSON impreso en varias líneas (de ``{`` a ``}``).

    Args:
        lines (Sequence[str]): Salida completa, línea a línea.

    Returns:
        str: Texto del objeto, o ``""`` si no hay ninguno.
    """
    starts = [i for i, line in enumerate(lines) if line.rstrip() == "{"]
    return "\n".join(lines[starts[-1]:]) if starts else ""


def parse_pack_summary(lines: Sequence[str]) -> PackSummary:
    """Lee el resumen JSON con el que termina ``ampr_pack.py pack``.

    Args:
        lines (Sequence[str]): Salida completa del empaquetado.

    Returns:
        PackSummary: Archivos sueltos y tamaños.

    Raises:
        ValueError: Si no hay resumen o no tiene la forma esperada.
    """
    data = json.loads(json_tail(lines) or "null")
    if not isinstance(data, dict) or not isinstance(data.get("loose_paths"), list):
        raise ValueError("ampr_pack.py no devolvió el resumen esperado")
    return PackSummary(
        loose_paths=tuple(str(path) for path in data["loose_paths"]),
        files_packed=int(data.get("files_packed", 0)),
        logical_bytes=int(data.get("logical_bytes", 0)),
        stored_bytes=int(data.get("stored_bytes", 0)),
    )
