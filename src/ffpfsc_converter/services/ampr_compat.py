"""Detección de si un juego admite LZ4 (formato AMPR).

Solo sirve si el juego lee sus recursos con ``libSceAmpr``: se busca ese nombre en
``eboot.bin`` y en los módulos de ``sce_module/``. ``libkernel`` aparece en todo
ejecutable legible, así que si se vio y falta ``libSceAmpr`` el juego no la usa;
si no se vio ninguno, el ejecutable está cifrado y no se puede saber.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ffpfsc_converter.config import GAME_ROOT_MARKER
from ffpfsc_converter.domain.lz4 import Lz4Compat

_NEEDLE = b"libSceAmpr"
_WITNESS = b"libkernel"
_CHUNK = 4 * 1024 * 1024
_MODULE_SUFFIXES = (".prx", ".sprx")


@dataclass
class _Scan:
    """Lo encontrado al recorrer los ejecutables.

    Attributes:
        found (bool): Algún ejecutable importa ``libSceAmpr``.
        readable (bool): Algún ejecutable mostró ``libkernel`` (no está cifrado).
    """

    found: bool = False
    readable: bool = False


def detect_compat(game_root: Path) -> Lz4Compat:
    """Decide si el juego de una carpeta admite LZ4.

    Args:
        game_root (Path): Carpeta con ``eboot.bin`` (una imagen no se puede revisar).

    Returns:
        Lz4Compat: ``YES`` si importa ``libSceAmpr``; ``NO`` si sus ejecutables se leen y
        no la importan; ``UNKNOWN`` si no se pueden leer o no es una carpeta.
    """
    if not game_root.is_dir():
        return Lz4Compat.UNKNOWN
    scan = _Scan()
    modules = sorted((game_root / "sce_module").glob("*"))
    for path in [game_root / GAME_ROOT_MARKER, *modules]:
        if path.suffix.lower() in _MODULE_SUFFIXES or path.name == GAME_ROOT_MARKER:
            _scan_file(path, scan)
        if scan.found:
            return Lz4Compat.YES
    return Lz4Compat.NO if scan.readable else Lz4Compat.UNKNOWN


def _scan_file(path: Path, scan: _Scan) -> None:
    """Busca ``libSceAmpr`` y ``libkernel`` en un archivo, por bloques.

    Modifica ``scan`` a propósito. Guarda una cola entre bloques para no perder un
    nombre partido entre dos lecturas; un archivo ilegible se ignora.

    Args:
        path (Path): Ejecutable a revisar.
        scan (_Scan): Resultado acumulado.
    """
    tail = b""
    try:
        with path.open("rb") as fh:
            while chunk := fh.read(_CHUNK):
                data = tail + chunk
                scan.readable = scan.readable or _WITNESS in data
                if _NEEDLE in data:
                    scan.found = True
                    return
                tail = data[-len(_NEEDLE):]
    except OSError:
        return
