"""Descarga los archivos de terceros que usa la compresión LZ4 (lo llama el instalador).

Baja ``exfat2ampr.elf`` y lo necesario de ``ampr_emu`` desde la página oficial de
cada proyecto, comprueba su SHA-256 y los deja en ``third_party/``. Si algo falla
(por ejemplo, sin internet) lo avisa y sigue: el resto de la app funciona igual.

Uso: ``python tools/fetch_third_party.py``
"""
from __future__ import annotations

import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

from ffpfsc_converter.config import THIRD_PARTY_ASSETS
from ffpfsc_converter.domain.third_party import ThirdPartyAsset
from ffpfsc_converter.infrastructure.third_party import Opener, fetch, third_party_dir


def fetch_all(assets: Sequence[ThirdPartyAsset], root: Path,
              opener: Opener | None = None) -> list[str]:
    """Descarga cada archivo y junta los que fallaron, sin detenerse en el primero.

    Args:
        assets (Sequence[ThirdPartyAsset]): Archivos a obtener.
        root (Path): Carpeta de terceros.
        opener (Opener | None): Abre las URL; ``None`` usa la red real.

    Returns:
        list[str]: Mensajes de los que no se pudieron obtener (vacía si todo salió bien).
    """
    failures: list[str] = []
    for asset in assets:
        try:
            done = fetch(asset, root, opener)
        except (OSError, zipfile.BadZipFile) as exc:
            failures.append(f"{asset.name}: {exc}")
            print(f"  ✗ {asset.name}: {exc}")
            continue
        print(f"  ✓ {asset.name}" + ("" if done else " (ya estaba)"))
    return failures


def main() -> int:
    """Descarga todo en ``third_party/`` y resume el resultado.

    Returns:
        int: ``0`` si todo quedó listo; ``1`` si faltó algo.
    """
    print("Descargando los componentes de LZ4 (exfat2ampr y ampr_emu)…")
    failures = fetch_all(THIRD_PARTY_ASSETS, third_party_dir())
    if failures:
        print("Aviso: faltan componentes de LZ4. La app funciona igual; vuelve a ejecutar "
              "el instalador con conexión a internet para usar LZ4.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
