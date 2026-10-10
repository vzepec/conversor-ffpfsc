"""Consulta a GitHub la última versión publicada de la app."""
from __future__ import annotations

import json
import urllib.request

from ffpfsc_converter import __version__


def fetch_latest_release(url: str, timeout: float) -> dict[str, object]:
    """Descarga la descripción de la última versión publicada.

    Args:
        url (str): Dirección de la API de GitHub (``releases/latest``).
        timeout (float): Segundos máximos de espera.

    Returns:
        dict[str, object]: Respuesta JSON de GitHub.

    Raises:
        OSError: Si no hay red, se agotó el tiempo o GitHub respondió con un error
            (por ejemplo, 404 si aún no hay versiones publicadas).
        ValueError: Si la respuesta no es un JSON válido.
    """
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"conversor-ffpfsc/{__version__}",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("respuesta inesperada de GitHub")
    return data
