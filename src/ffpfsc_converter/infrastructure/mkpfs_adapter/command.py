"""Construcción de la línea de comandos de ``mkpfs pack``."""
from __future__ import annotations

import sys

from ffpfsc_converter.config import COMPRESSION_BACKEND
from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions, SourceKind


def build_pack_command(
    job: ConversionJob,
    options: ConversionOptions,
    python_executable: str = sys.executable,
) -> list[str]:
    """Construye la línea de comandos de ``mkpfs pack`` para un trabajo.

    Se usa el mismo intérprete que la aplicación para que MkPFS corra dentro
    del mismo entorno virtual, y la carpeta de destino como carpeta temporal
    para no llenar ``/tmp`` con imágenes de decenas de GB.

    Args:
        job (ConversionJob): Trabajo a convertir.
        options (ConversionOptions): Nivel de compresión, núcleos y verificación.
        python_executable (str): Intérprete de Python que ejecutará MkPFS.

    Returns:
        list[str]: Argumentos listos para ``subprocess.Popen``.
    """
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
