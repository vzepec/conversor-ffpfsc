"""Archivos de terceros que el instalador descarga (no se versionan con la app)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThirdPartyAsset:
    """Archivo publicado por otro proyecto, fijado a una versión y a su SHA-256.

    Attributes:
        name (str): Nombre para los mensajes del instalador.
        url (str): Descarga oficial (página de releases del proyecto).
        sha256 (str): Huella esperada del archivo descargado.
        target (str): Destino dentro de ``third_party/`` (archivo, o carpeta si se extrae).
        extract_prefix (str): Si no está vacío, la descarga es un ``.zip`` y se extraen
            solo los miembros que empiezan con este prefijo (sin él) en ``target``.
    """

    name: str
    url: str
    sha256: str
    target: str
    extract_prefix: str = ""

    @property
    def is_archive(self) -> bool:
        """Indica si hay que extraer parte de un ``.zip`` en vez de guardar el archivo.

        Returns:
            bool: ``True`` si ``extract_prefix`` no está vacío.
        """
        return bool(self.extract_prefix)
