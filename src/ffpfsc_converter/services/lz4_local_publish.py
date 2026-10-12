"""Publicación de la carpeta LZ4: paquetes, índice, biblioteca del juego y renombre final.

Los archivos sueltos pueden ser enlaces duros al juego original: aquí nunca se escribe
dentro de ellos, y la carpeta anterior solo se reemplaza cuando la nueva está completa.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ffpfsc_converter.config import AMPR_FAKELIB_DIR, AMPR_INDEX_FILE, LZ4_BACKUP_SUFFIX
from ffpfsc_converter.services.lz4_local_files import Lz4Workspace


def finish_folder(ws: Lz4Workspace, runtime: Path) -> None:
    """Completa la carpeta final y la publica en su ruta definitiva.

    Mueve los paquetes y su índice, copia ``ampr_emu.index`` y la biblioteca que los
    lee (``fakelib/libSceAmpr.sprx``) y publica ``<salida>.parcial`` como ``<salida>``
    (la interfaz ya confirmó reemplazar una salida anterior).

    Args:
        ws (Lz4Workspace): Rutas de la conversión.
        runtime (Path): ``libSceAmpr.sprx`` instalado.

    Raises:
        OSError: Si falla algún movimiento o copia.
    """
    paths = ws.pack_paths
    for item in paths.output.iterdir():
        shutil.move(str(item), ws.partial / item.name)
    _replace_file(paths.index, ws.partial / AMPR_INDEX_FILE)
    fakelib = ws.partial / AMPR_FAKELIB_DIR
    fakelib.mkdir(exist_ok=True)
    _replace_file(runtime, fakelib / runtime.name)
    _publish(ws.partial, ws.output)


def _publish(partial: Path, output: Path) -> None:
    """Renombra la carpeta nueva a su ruta final sin perder la anterior si algo falla.

    Args:
        partial (Path): Carpeta recién armada.
        output (Path): Ruta definitiva (puede tener una conversión anterior).

    Raises:
        OSError: Si no se puede renombrar (la anterior queda restaurada).
    """
    backup = output.with_name(f"{output.name}{LZ4_BACKUP_SUFFIX}")
    shutil.rmtree(backup, ignore_errors=True)
    if output.exists():
        output.rename(backup)
    try:
        partial.rename(output)
    except OSError:
        if backup.exists():
            backup.rename(output)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def _replace_file(source: Path, dest: Path) -> None:
    """Escribe un archivo propio en el resultado sin tocar un posible enlace al original.

    ``dest`` puede ser un enlace duro a un archivo del juego (por ejemplo, su propio
    ``ampr_emu.index`` o ``fakelib/libSceAmpr.sprx``): escribir encima cambiaría el
    original, así que primero se quita la entrada y luego se copia.

    Args:
        source (Path): Archivo a copiar.
        dest (Path): Destino en la carpeta parcial.

    Raises:
        OSError: Si falla la copia.
    """
    dest.unlink(missing_ok=True)
    shutil.copy2(source, dest)
