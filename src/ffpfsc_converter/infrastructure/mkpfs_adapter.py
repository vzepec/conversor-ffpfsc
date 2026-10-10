"""Adaptador a MkPFS: construcción del comando, ejecución y lectura de metadatos.

Todo el conocimiento sobre la CLI y la API interna de MkPFS está aquí. Si
MkPFS cambia, este es el único archivo que debería tocarse.
"""
from __future__ import annotations

import contextlib
import os
import re
import signal
import subprocess
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

from ffpfsc_converter.config import COMPRESSION_BACKEND
from ffpfsc_converter.domain.models import (
    ConversionJob,
    ConversionOptions,
    GameInfo,
    ProgressUpdate,
    SourceKind,
)

#: Ejemplo: ``[2/4] 37% compress @ 512.3 MB/s``
_PROGRESS_RE = re.compile(r"(\d{1,3})% (\w+)(?: @ ([\d.]+ \w+/s))?")
_LINE_SPLIT_RE = re.compile(rb"[\r\n]")
_READ_CHUNK = 4096


# ------------------------------------------------------------------ comando
def build_pack_command(
    job: ConversionJob,
    options: ConversionOptions,
    python_executable: str = sys.executable,
) -> list[str]:
    """Construye la línea de comandos de ``mkpfs pack`` para un trabajo."""
    cmd = [
        python_executable, "-u", "-m", "mkpfs", "pack", job.kind.value,
        "--compression-backend", COMPRESSION_BACKEND,
        "--compression-level", str(options.compression_level),
        "--cpu-count", str(options.cpu_count),
        "--no-adjust-output-file-extension",
        "--temp-folder", str(job.output.parent),
    ]
    if job.kind is SourceKind.FOLDER:
        cmd.append("--require-game-files")
    cmd.append("--verify" if options.full_verify else "--verify-structure")
    cmd += [str(job.game_root), str(job.output)]
    return cmd


# ------------------------------------------------------------------- salida
def parse_progress(line: str) -> ProgressUpdate | None:
    """Interpreta una línea de progreso de MkPFS; ``None`` si no lo es."""
    if not line.startswith("["):
        return None
    match = _PROGRESS_RE.search(line)
    if not match:
        return None
    return ProgressUpdate(int(match.group(1)), match.group(2), match.group(3))


def split_lines(chunks: Iterable[bytes]) -> Iterator[str]:
    """Convierte bloques de bytes en líneas no vacías.

    MkPFS redibuja su barra de progreso con ``\\r``, así que se corta tanto
    en ``\\r`` como en ``\\n``.
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


class PackProcess:
    """Proceso ``mkpfs pack`` en ejecución.

    Se lanza en su propia sesión para poder terminar también a sus hijos
    (MkPFS usa varios procesos de compresión).
    """

    def __init__(self, command: list[str]) -> None:
        self._proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            bufsize=0,
        )

    def lines(self) -> Iterator[str]:
        stdout = self._proc.stdout
        assert stdout is not None
        yield from split_lines(iter(lambda: stdout.read(_READ_CHUNK), b""))

    def wait(self) -> int:
        return self._proc.wait()

    def terminate(self) -> None:
        if self._proc.poll() is not None:
            return
        with contextlib.suppress(OSError):
            os.killpg(self._proc.pid, signal.SIGTERM)


# --------------------------------------------------------------- metadatos
def read_metadata(target: Path) -> GameInfo:
    """Lee los metadatos usando el lector de MkPFS (carpeta, .exfat o .ffpkg)."""
    from mkpfs.game_metadata import read_game_metadata

    meta = read_game_metadata(target)
    return GameInfo(meta.game_title, meta.title_id.strip("-"), meta.version)


def read_exfat_member(image: Path, rel_path: str, max_bytes: int) -> bytes | None:
    """Devuelve el contenido de ``rel_path`` dentro de una imagen exFAT, o ``None``."""
    from mkpfs.exfat import ExfatReader

    wanted = rel_path.lower()
    with image.open("rb") as fh:
        reader = ExfatReader(fh)
        for entry in reader.iter_files():
            if entry.rel_path.lower() == wanted and entry.length < max_bytes:
                return b"".join(reader.read_file(entry))
    return None
