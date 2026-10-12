"""Perfil genérico de compresión LZ4 (AMPR) para un juego, sin trazas.

Decide archivo por archivo qué se empaqueta y qué queda tal cual, sin distinguir
mayúsculas (las reglas de ``ampr_pack.py`` sí las distinguen), y le pasa listas
exactas en archivos ``include_from`` junto al TOML.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath

from ffpfsc_converter.config import (
    AMPR_AUDIO_TOP_DIRS,
    AMPR_LOOSE_EXTENSIONS,
    AMPR_LOOSE_NAMES,
    AMPR_LOOSE_PREFIXES,
    AMPR_LOOSE_TOP_DIRS,
    LZ4_FAST_MAX_LEVEL,
)

#: Nombres de las listas que acompañan al TOML (rutas relativas a él).
COMPRESS_LIST = "compress.txt"
AUDIO_LIST = "audio.txt"
_GLOB_SPECIAL = "*?["


class AmprAction(Enum):
    """Qué hacer con un archivo del juego."""

    LOOSE = "loose"        # se copia tal cual
    COMPRESS = "compress"  # bloques de 64 KiB, lectura mixta
    AUDIO = "audio"        # bloques de 16 KiB, lectura al azar


@dataclass(frozen=True)
class AmprProfile:
    """Perfil listo para escribir junto a la carpeta de trabajo.

    Attributes:
        toml (str): Contenido del ``profile.toml``.
        compress (tuple[str, ...]): Rutas para ``COMPRESS_LIST`` (ya escapadas).
        audio (tuple[str, ...]): Rutas para ``AUDIO_LIST`` (ya escapadas).
    """

    toml: str
    compress: tuple[str, ...]
    audio: tuple[str, ...]


def classify(relative: str) -> AmprAction:
    """Clasifica un archivo del juego según las reglas genéricas.

    Args:
        relative (str): Ruta relativa a la raíz del juego, con ``/``.

    Returns:
        AmprAction: Suelto, comprimido o comprimido como audio.
    """
    parts = PurePosixPath(relative.lower()).parts
    name = parts[-1] if parts else ""
    if (len(parts) < 2 or name in AMPR_LOOSE_NAMES or parts[0] in AMPR_LOOSE_TOP_DIRS
            or PurePosixPath(name).suffix in AMPR_LOOSE_EXTENSIONS
            or name.startswith(AMPR_LOOSE_PREFIXES)):
        return AmprAction.LOOSE
    return AmprAction.AUDIO if parts[0] in AMPR_AUDIO_TOP_DIRS else AmprAction.COMPRESS


def escape_glob(relative: str) -> str:
    """Escapa una ruta para que ``fnmatch`` la tome literal (``[`` → ``[[]``).

    Args:
        relative (str): Ruta relativa.

    Returns:
        str: Patrón que solo coincide con esa ruta.
    """
    return "".join(f"[{char}]" if char in _GLOB_SPECIAL else char for char in relative)


def build_profile(files: Iterable[str], level: int, workers: int) -> AmprProfile:
    """Arma el perfil TOML y las listas de archivos a empaquetar.

    Args:
        files (Iterable[str]): Rutas relativas de todos los archivos del juego.
        level (int): Nivel LZ4 (1-4 rápido, 5-12 HC).
        workers (int): Procesos de compresión.

    Returns:
        AmprProfile: TOML y listas.
    """
    groups: dict[AmprAction, list[str]] = {AmprAction.COMPRESS: [], AmprAction.AUDIO: []}
    for relative in sorted(files):
        action = classify(relative)
        if action is not AmprAction.LOOSE:
            groups[action].append(escape_glob(relative))
    return AmprProfile(_toml(level, workers), tuple(groups[AmprAction.COMPRESS]),
                       tuple(groups[AmprAction.AUDIO]))


def _toml(level: int, workers: int) -> str:
    """Escribe el TOML: todo suelto salvo las listas, deduplicado y con auto-suelto.

    Args:
        level (int): Nivel LZ4.
        workers (int): Procesos de compresión.

    Returns:
        str: Contenido del perfil.
    """
    mode = "fast" if level <= LZ4_FAST_MAX_LEVEL else "hc"
    return f"""# Perfil genérico generado por Conversor FFPFSC (sin trazas del juego).
[pack]
default_action = "loose"
default_block_size = "64KiB"
workers = {max(1, workers)}
compression_mode = "{mode}"
compression_level = {level}
acceleration = 1
deduplicate = true
auto_loose_large_files = true

[[rule]]
action = "compress"
include_from = ["{COMPRESS_LIST}"]
block_size = "64KiB"
layout = "mixed"

[[rule]]
action = "compress"
include_from = ["{AUDIO_LIST}"]
block_size = "16KiB"
layout = "random"
hot = true
"""
