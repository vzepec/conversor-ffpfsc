"""Comprueba en segundo plano si hay una versión más nueva de la app.

Es *best effort*: sin red, con GitHub caído o sin versiones publicadas no se
muestra nada y la app funciona igual.
"""
from __future__ import annotations

import re
import threading
from collections.abc import Callable, Mapping

from ffpfsc_converter import __version__
from ffpfsc_converter.config import LATEST_RELEASE_URL, UPDATE_CHECK_TIMEOUT_SECONDS
from ffpfsc_converter.domain.events import EventSink
from ffpfsc_converter.domain.update import ReleaseInfo, UpdateAvailable
from ffpfsc_converter.infrastructure.release_feed import fetch_latest_release

_VERSION = re.compile(r"v?(\d+(?:\.\d+)*)")
#: Obtiene la respuesta de GitHub (en la app, ``fetch_latest_release``).
ReleaseFetcher = Callable[[], Mapping[str, object]]


def parse_version(text: str) -> tuple[int, ...] | None:
    """Convierte un número de versión en una tupla comparable.

    Args:
        text (str): Por ejemplo ``"v1.3.0"`` o ``"1.2"``.

    Returns:
        tuple[int, ...] | None: ``(1, 3, 0)``, o ``None`` si no es una versión válida
        (las versiones previas como ``"1.3.0-beta"`` no cuentan).
    """
    match = _VERSION.fullmatch(text.strip())
    if match is None:
        return None
    numbers = [int(part) for part in match.group(1).split(".")]
    while len(numbers) > 1 and numbers[-1] == 0:
        numbers.pop()
    return tuple(numbers)


def release_from_json(data: Mapping[str, object]) -> ReleaseInfo | None:
    """Extrae la versión y su página de la respuesta de GitHub.

    Args:
        data (Mapping[str, object]): JSON de ``releases/latest``.

    Returns:
        ReleaseInfo | None: Versión publicada, o ``None`` si es un borrador, una
        versión previa o la respuesta no trae los datos necesarios.
    """
    tag, url = data.get("tag_name"), data.get("html_url")
    if data.get("draft") or data.get("prerelease"):
        return None
    if not isinstance(tag, str) or not isinstance(url, str) or parse_version(tag) is None:
        return None
    return ReleaseInfo(tag.strip().lstrip("v"), url)


def newer_release(fetch: ReleaseFetcher, current: str = __version__) -> ReleaseInfo | None:
    """Consulta la última versión y la devuelve solo si es más nueva que la instalada.

    Args:
        fetch (ReleaseFetcher): Obtiene la respuesta de GitHub.
        current (str): Versión instalada.

    Returns:
        ReleaseInfo | None: Versión más nueva, o ``None`` si no hay o no se pudo consultar.
    """
    try:
        release = release_from_json(fetch())
    except (OSError, ValueError):
        return None
    installed = parse_version(current)
    if release is None or installed is None:
        return None
    latest = parse_version(release.version)
    return release if latest is not None and latest > installed else None


def start_update_check(emit: EventSink, fetch: ReleaseFetcher | None = None) -> threading.Thread:
    """Lanza la comprobación en un hilo y publica ``UpdateAvailable`` si hay versión nueva.

    Args:
        emit (EventSink): Cola de eventos de la ventana.
        fetch (ReleaseFetcher | None): Consulta a usar; ``None`` = la API de GitHub.

    Returns:
        threading.Thread: Hilo ya iniciado.
    """
    def default_fetch() -> Mapping[str, object]:
        """Consulta la API de GitHub con la dirección y el tiempo de espera configurados.

        Returns:
            Mapping[str, object]: Respuesta JSON.
        """
        return fetch_latest_release(LATEST_RELEASE_URL, UPDATE_CHECK_TIMEOUT_SECONDS)

    def run() -> None:
        """Consulta y avisa si corresponde."""
        release = newer_release(fetch or default_fetch)
        if release is not None:
            emit(UpdateAvailable(release))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread
