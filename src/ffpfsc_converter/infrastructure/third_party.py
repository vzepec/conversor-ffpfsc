"""Archivos de terceros: dónde quedan y cómo se descargan y verifican.

El instalador los descarga en ``third_party/`` (junto a la app, fuera de Git) desde
la página oficial de cada proyecto. Nada se coloca si su SHA-256 no coincide con
el fijado en ``config.THIRD_PARTY_ASSETS``.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from ffpfsc_converter.config import (
    THIRD_PARTY_CHUNK_BYTES,
    THIRD_PARTY_DIR_NAME,
    THIRD_PARTY_TIMEOUT_SECONDS,
)
from ffpfsc_converter.domain.third_party import ThirdPartyAsset

#: Abre una URL y devuelve un flujo binario (se sustituye en los tests).
Opener = Callable[[str], BinaryIO]
#: Archivo que guarda la huella del ``.zip`` del que salió una carpeta extraída.
_STAMP = ".sha256"


class ChecksumMismatchError(OSError):
    """La descarga no coincide con la huella fijada: no se usa."""


def third_party_dir() -> Path:
    """Calcula la carpeta de archivos de terceros (junto a ``src/``).

    Returns:
        Path: ``<carpeta de la app>/third_party``.
    """
    return Path(__file__).resolve().parents[3] / THIRD_PARTY_DIR_NAME


def installed(relative: str, root: Path | None = None) -> Path | None:
    """Devuelve un archivo o carpeta de terceros si el instalador lo dejó.

    Args:
        relative (str): Ruta dentro de ``third_party/`` (por ejemplo ``config.AMPR_RUNTIME_FILE``).
        root (Path | None): Carpeta de terceros; ``None`` usa :func:`third_party_dir`.

    Returns:
        Path | None: Ruta existente, o ``None`` si falta.
    """
    path = (root or third_party_dir()) / relative
    return path if path.exists() else None


def is_current(asset: ThirdPartyAsset, root: Path) -> bool:
    """Indica si el archivo ya está y corresponde a la versión fijada.

    Args:
        asset (ThirdPartyAsset): Archivo esperado.
        root (Path): Carpeta de terceros.

    Returns:
        bool: ``True`` si no hace falta descargarlo otra vez.
    """
    target = root / asset.target
    if asset.is_archive:
        stamp = target / _STAMP
        return stamp.is_file() and stamp.read_text(encoding="ascii").strip() == asset.sha256
    return target.is_file() and file_sha256(target) == asset.sha256


def fetch(asset: ThirdPartyAsset, root: Path, opener: Opener | None = None) -> bool:
    """Descarga, verifica y coloca un archivo de terceros.

    Args:
        asset (ThirdPartyAsset): Archivo a obtener.
        root (Path): Carpeta de terceros (se crea si falta).
        opener (Opener | None): Abre la URL; ``None`` usa la red real.

    Returns:
        bool: ``True`` si se descargó; ``False`` si ya estaba al día.

    Raises:
        OSError: Si falla la descarga o la escritura.
        ChecksumMismatchError: Si la huella no coincide (no se coloca nada).
        zipfile.BadZipFile: Si el ``.zip`` está dañado.
    """
    if is_current(asset, root):
        return False
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as work:
        download = Path(work) / "download"
        _download(asset.url, download, opener or _open_url)
        digest = file_sha256(download)
        if digest != asset.sha256:
            raise ChecksumMismatchError(f"{asset.name}: SHA-256 {digest} ≠ {asset.sha256}")
        if asset.is_archive:
            _extract(download, asset, root)
        else:
            target = root / asset.target
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(download), target)
    return True


def file_sha256(path: Path) -> str:
    """Calcula el SHA-256 de un archivo por bloques.

    Args:
        path (Path): Archivo.

    Returns:
        str: Huella en hexadecimal.

    Raises:
        OSError: Si no se puede leer.
    """
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(THIRD_PARTY_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _open_url(url: str) -> BinaryIO:
    """Abre una URL con el tiempo de espera de las descargas.

    Args:
        url (str): Dirección HTTPS.

    Returns:
        BinaryIO: Respuesta para leer por bloques.

    Raises:
        OSError: Si no hay conexión o el servidor responde con error.
    """
    return urllib.request.urlopen(url, timeout=THIRD_PARTY_TIMEOUT_SECONDS)


def _download(url: str, dest: Path, opener: Opener) -> None:
    """Copia el contenido de una URL a un archivo local.

    Args:
        url (str): Descarga.
        dest (Path): Archivo de destino.
        opener (Opener): Abre la URL.

    Raises:
        OSError: Si falla la red o la escritura.
    """
    with opener(url) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out, THIRD_PARTY_CHUNK_BYTES)


def _extract(archive: Path, asset: ThirdPartyAsset, root: Path) -> None:
    """Extrae del ``.zip`` solo los miembros bajo ``extract_prefix`` y deja la huella.

    Reemplaza la carpeta anterior por completo para no mezclar versiones.

    Args:
        archive (Path): ``.zip`` ya verificado.
        asset (ThirdPartyAsset): Archivo con el prefijo y la carpeta de destino.
        root (Path): Carpeta de terceros.

    Raises:
        OSError: Si falla la escritura o un miembro intenta salir de la carpeta.
        zipfile.BadZipFile: Si el ``.zip`` está dañado.
    """
    target = root / asset.target
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            name = member.filename
            if member.is_dir() or not name.startswith(asset.extract_prefix):
                continue
            dest = (target / name[len(asset.extract_prefix):]).resolve()
            if target.resolve() not in dest.parents:
                raise OSError(f"Ruta no válida dentro del .zip: {name}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
    (target / _STAMP).write_text(asset.sha256, encoding="ascii")
