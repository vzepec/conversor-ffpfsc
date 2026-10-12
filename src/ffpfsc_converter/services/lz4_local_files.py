"""Archivos de la conversión LZ4 en el PC: carpeta de trabajo, perfil y carpeta final.

Todo se escribe junto a la salida (nunca en ``/tmp`` ni en el juego original): la
carpeta final se arma en ``<salida>.parcial`` y solo al terminar se renombra.
"""
from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from ffpfsc_converter.config import (
    AMPR_INDEX_FILE,
    LZ4_LEVEL_BY_PRESET,
    LZ4_PARTIAL_SUFFIX,
    LZ4_SEPARATE_NAME_SUFFIX,
    LZ4_WORK_SUFFIX,
)
from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions, OutputFormat
from ffpfsc_converter.infrastructure.ampr_tools import PackPaths
from ffpfsc_converter.services.ampr_profile import AUDIO_LIST, COMPRESS_LIST, AmprProfile

#: Recibe los bytes copiados hasta ahora; devuelve ``False`` para detener la copia.
CopyProgress = Callable[[int], bool]
_PROFILE_NAME = "profile.toml"
_PACKS_DIR = "paquetes"


@dataclass(frozen=True)
class Lz4Workspace:
    """Rutas de una conversión LZ4 en el PC.

    Attributes:
        root (Path): Juego original (solo se lee).
        work (Path): Carpeta temporal con índice, perfil y paquetes.
        partial (Path): Carpeta final mientras se arma.
        output (Path): Carpeta final.
    """

    root: Path
    work: Path
    partial: Path
    output: Path

    @property
    def pack_paths(self) -> PackPaths:
        """Rutas que necesita ``ampr_pack.py``.

        Returns:
            PackPaths: Juego, índice, perfil y carpeta de paquetes.
        """
        return PackPaths(self.root, self.work / AMPR_INDEX_FILE, self.work / _PROFILE_NAME,
                         self.work / _PACKS_DIR)


def lz4_output_path(job: ConversionJob) -> Path:
    """Calcula la carpeta LZ4 de un trabajo (junto a donde iría su ``.ffpfsc``).

    Args:
        job (ConversionJob): Trabajo.

    Returns:
        Path: ``<carpeta de salida>/<nombre>-LZ4``.
    """
    return job.output.with_name(f"{job.output.stem}{LZ4_SEPARATE_NAME_SUFFIX}")


def planned_output(job: ConversionJob, options: ConversionOptions) -> Path:
    """Calcula dónde quedará el resultado según el formato.

    Args:
        job (ConversionJob): Trabajo.
        options (ConversionOptions): Opciones elegidas.

    Returns:
        Path: ``.ffpfsc`` o carpeta ``-LZ4``.
    """
    return lz4_output_path(job) if options.output_format is OutputFormat.LZ4 else job.output


def lz4_options(preset_level: int, cpu_count: int) -> ConversionOptions:
    """Arma las opciones de una conversión LZ4 a partir del modo elegido.

    Args:
        preset_level (int): Nivel del modo (el mismo que usa ``.ffpfsc``).
        cpu_count (int): Núcleos a usar.

    Returns:
        ConversionOptions: Formato LZ4 con su nivel equivalente.
    """
    return ConversionOptions(LZ4_LEVEL_BY_PRESET[preset_level], cpu_count, False,
                             output_format=OutputFormat.LZ4)


def workspace_for(job: ConversionJob) -> Lz4Workspace:
    """Arma las rutas de trabajo de un trabajo.

    Args:
        job (ConversionJob): Trabajo con ``game_root`` y ``output``.

    Returns:
        Lz4Workspace: Rutas (todavía no se crea nada).
    """
    output = lz4_output_path(job)
    return Lz4Workspace(job.game_root, output.with_name(f".{output.name}{LZ4_WORK_SUFFIX}"),
                        output.with_name(f"{output.name}{LZ4_PARTIAL_SUFFIX}"), output)


def relative_files(root: Path) -> list[str]:
    """Lista los archivos del juego con rutas relativas y ``/``, sin seguir enlaces.

    Args:
        root (Path): Carpeta del juego.

    Returns:
        list[str]: Rutas relativas de los archivos regulares.
    """
    found: list[str] = []
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            path = Path(dirpath, name)
            if path.is_file() and not path.is_symlink():
                found.append(path.relative_to(root).as_posix())
    return found


def write_profile(ws: Lz4Workspace, profile: AmprProfile) -> None:
    """Escribe el TOML y sus listas en la carpeta de trabajo.

    Args:
        ws (Lz4Workspace): Rutas de la conversión.
        profile (AmprProfile): Perfil generado.

    Raises:
        OSError: Si no se puede escribir.
    """
    config = ws.pack_paths.config
    config.write_text(profile.toml, encoding="utf-8")
    for name, lines in ((COMPRESS_LIST, profile.compress), (AUDIO_LIST, profile.audio)):
        (config.parent / name).write_text("".join(f"{line}\n" for line in lines),
                                          encoding="utf-8")


def copy_loose(ws: Lz4Workspace, loose: Iterable[str], progress: CopyProgress) -> bool:
    """Lleva al resultado los archivos que quedan sin empaquetar.

    En el mismo disco se enlazan (enlace duro: no ocupan espacio extra ni se toca su
    contenido); si no se puede (otro disco, exFAT…), se copian.

    Args:
        ws (Lz4Workspace): Rutas de la conversión.
        loose (Iterable[str]): Rutas relativas que indicó ``ampr_pack.py``.
        progress (CopyProgress): Avance en bytes; si devuelve ``False`` se detiene.

    Returns:
        bool: ``True`` si se copió todo; ``False`` si se detuvo.

    Raises:
        OSError: Si falla la copia o una ruta sale de la carpeta del juego.
    """
    copied = 0
    for relative in loose:
        source, dest = ws.root / relative, ws.partial / relative
        if ws.root.resolve() not in source.resolve().parents:
            raise OSError(f"Ruta fuera del juego: {relative}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        _link_or_copy(source, dest)
        copied += source.stat().st_size
        if not progress(copied):
            return False
    return True


def _link_or_copy(source: Path, dest: Path) -> None:
    """Enlaza un archivo del juego en el resultado o, si no se puede, lo copia.

    Args:
        source (Path): Archivo original (solo se lee).
        dest (Path): Ruta en la carpeta parcial.

    Raises:
        OSError: Si tampoco se puede copiar.
    """
    try:
        os.link(source, dest)
    except OSError:
        shutil.copy2(source, dest)


def folder_size(folder: Path) -> int:
    """Suma el tamaño de los archivos de una carpeta.

    Args:
        folder (Path): Carpeta.

    Returns:
        int: Bytes totales (``0`` si no existe).
    """
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


def discard(ws: Lz4Workspace) -> None:
    """Borra la carpeta de trabajo y la salida a medias (nunca la salida final).

    La salida final solo aparece al renombrar, en el último paso: si algo falla antes,
    una conversión anterior en esa ruta queda intacta.

    Args:
        ws (Lz4Workspace): Rutas de la conversión.
    """
    shutil.rmtree(ws.work, ignore_errors=True)
    shutil.rmtree(ws.partial, ignore_errors=True)
