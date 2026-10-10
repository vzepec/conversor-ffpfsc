"""Interpretación de la salida de texto de MkPFS."""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from ffpfsc_converter.domain.models import ProgressUpdate

#: Ejemplo: ``[2/4] 37% compress @ 512.3 MB/s``
_PROGRESS_RE = re.compile(r"(\d{1,3})% (\w+)(?: @ ([\d.]+ \w+/s))?")
_LINE_SPLIT_RE = re.compile(rb"[\r\n]")


def parse_progress(line: str) -> ProgressUpdate | None:
    """Interpreta una línea de progreso de MkPFS.

    Args:
        line (str): Línea de salida ya decodificada y sin espacios extremos.

    Returns:
        ProgressUpdate | None: El progreso leído, o ``None`` si la línea no es
        de progreso (las de progreso empiezan con ``[``).
    """
    if not line.startswith("["):
        return None
    match = _PROGRESS_RE.search(line)
    if not match:
        return None
    return ProgressUpdate(int(match.group(1)), match.group(2), match.group(3))


def split_lines(chunks: Iterable[bytes]) -> Iterator[str]:
    """Convierte bloques de bytes en líneas de texto no vacías.

    MkPFS redibuja su barra de progreso con ``\\r``, así que se corta tanto en
    ``\\r`` como en ``\\n``. Una línea puede llegar repartida entre bloques.

    Args:
        chunks (Iterable[bytes]): Bloques leídos de la salida del proceso.

    Yields:
        str: Cada línea decodificada en UTF-8, sin espacios extremos.
    """
    buffer = b""
    for chunk in chunks:
        buffer += chunk
        *complete, buffer = _LINE_SPLIT_RE.split(buffer)
        for raw in complete:
            line = raw.decode("utf-8", "replace").strip()
            if line:
                yield line
    tail = buffer.decode("utf-8", "replace").strip()
    if tail:
        yield tail
