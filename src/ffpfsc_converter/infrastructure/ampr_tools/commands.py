"""Líneas de comandos de las herramientas en Python de ampr_emu (``third_party/``)."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from ffpfsc_converter.config import AMPR_INDEX_SCRIPT, AMPR_PACK_SCRIPT


@dataclass(frozen=True)
class PackPaths:
    """Rutas de un empaquetado LZ4.

    Attributes:
        root (Path): Carpeta del juego original (``/app0``); nunca se modifica.
        index (Path): ``ampr_emu.index`` generado para ``root``.
        config (Path): Perfil TOML con las reglas.
        output (Path): Carpeta donde quedan los ``.pak`` y su índice.
    """

    root: Path
    index: Path
    config: Path
    output: Path


@dataclass(frozen=True)
class AmprTools:
    """Herramientas instaladas y el intérprete que las ejecuta.

    Attributes:
        tools_dir (Path): Carpeta ``python-tools`` de ampr_emu.
        python (str): Intérprete (el de la app, que ya tiene el paquete ``lz4``).
    """

    tools_dir: Path
    python: str = sys.executable

    def _script(self, name: str) -> list[str]:
        """Arma el comienzo de un comando que ejecuta un script sin búfer de salida.

        Args:
            name (str): Script dentro de ``tools_dir``.

        Returns:
            list[str]: Intérprete, ``-u`` y ruta del script.
        """
        return [self.python, "-u", str(self.tools_dir / name)]

    def index_command(self, root: Path, output: Path) -> list[str]:
        """Comando que genera ``ampr_emu.index`` fuera del juego (no se toca el original).

        Args:
            root (Path): Carpeta del juego.
            output (Path): Archivo de índice a crear.

        Returns:
            list[str]: Argumentos para el proceso.
        """
        return [*self._script(AMPR_INDEX_SCRIPT), str(root), "--output", str(output)]

    def pack_command(self, paths: PackPaths, workers: int) -> list[str]:
        """Comando que crea los paquetes LZ4 según el perfil.

        Args:
            paths (PackPaths): Juego, índice, perfil y carpeta de salida.
            workers (int): Procesos de compresión.

        Returns:
            list[str]: Argumentos para el proceso.
        """
        return [*self._script(AMPR_PACK_SCRIPT), "pack", "--root", str(paths.root),
                "--ampr-index", str(paths.index), "--output", str(paths.output),
                "--config", str(paths.config), "--workers", str(max(1, workers))]

    def verify_command(self, index: Path, root: Path) -> list[str]:
        """Comando que comprueba cada bloque y lo compara byte a byte con el original.

        Args:
            index (Path): ``ampr_assets.index`` recién creado.
            root (Path): Carpeta del juego original.

        Returns:
            list[str]: Argumentos para el proceso.
        """
        return [*self._script(AMPR_PACK_SCRIPT), "verify", "--index", str(index),
                "--root", str(root)]
