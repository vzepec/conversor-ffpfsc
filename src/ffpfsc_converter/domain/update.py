"""Versiones publicadas de la app (aviso de actualización)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseInfo:
    """Versión publicada en GitHub.

    Attributes:
        version (str): Número de versión sin prefijo (``"1.3.0"``).
        url (str): Página de la versión, con las notas y los archivos de descarga.
    """

    version: str
    url: str


@dataclass(frozen=True)
class UpdateAvailable:
    """Hay una versión más nueva que la instalada.

    Attributes:
        release (ReleaseInfo): Versión disponible.
    """

    release: ReleaseInfo
