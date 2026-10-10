from __future__ import annotations

import json
import threading
from collections.abc import Iterator, Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ffpfsc_converter.domain.update import ReleaseInfo, UpdateAvailable
from ffpfsc_converter.infrastructure.release_feed import fetch_latest_release
from ffpfsc_converter.services import update_check as uc

RELEASE = {"tag_name": "v1.3.0", "html_url": "https://github.com/x/y/releases/tag/v1.3.0",
           "draft": False, "prerelease": False}


def test_parse_version() -> None:
    """Acepta el prefijo «v», ignora ceros finales y rechaza versiones previas."""
    assert uc.parse_version("v1.3.0") == (1, 3)
    assert uc.parse_version("1.10") > uc.parse_version("1.9.9")  # type: ignore[operator]
    assert uc.parse_version("1.3.0-beta") is None
    assert uc.parse_version("nada") is None


def test_release_from_json() -> None:
    """Lee la versión y su página; descarta borradores y versiones previas."""
    assert uc.release_from_json(RELEASE) == ReleaseInfo("1.3.0", RELEASE["html_url"])
    assert uc.release_from_json({**RELEASE, "prerelease": True}) is None
    assert uc.release_from_json({"tag_name": "v1.3.0"}) is None


def test_newer_release_compares_with_installed() -> None:
    """Solo avisa si la versión publicada es mayor que la instalada."""
    assert uc.newer_release(lambda: RELEASE, current="1.2.0") == ReleaseInfo(
        "1.3.0", RELEASE["html_url"])
    assert uc.newer_release(lambda: RELEASE, current="1.3.0") is None
    assert uc.newer_release(lambda: RELEASE, current="2.0.0") is None


def test_newer_release_ignores_network_errors() -> None:
    """Sin red o con una respuesta inválida no avisa nada (y no falla)."""
    def offline() -> Mapping[str, object]:
        """Simula que no hay conexión."""
        raise OSError("sin red")

    assert uc.newer_release(offline, current="1.0.0") is None


def test_start_update_check_emits_event() -> None:
    """La comprobación en segundo plano publica UpdateAvailable."""
    events: list[object] = []
    uc.start_update_check(events.append, lambda: {**RELEASE, "tag_name": "v99.0.0"}).join(5)
    assert events == [UpdateAvailable(ReleaseInfo("99.0.0", RELEASE["html_url"]))]


class _Handler(BaseHTTPRequestHandler):
    """Servidor de prueba: responde la última versión o 404."""

    def do_GET(self) -> None:
        """Responde según la ruta pedida."""
        if self.path != "/latest":
            self.send_error(404)
            return
        body = json.dumps(RELEASE).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Silencia el registro del servidor."""


@pytest.fixture
def http_url() -> Iterator[str]:
    """Levanta un servidor HTTP local y devuelve su dirección."""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_fetch_latest_release(http_url: str) -> None:
    """Descarga el JSON de la versión y convierte los errores HTTP en OSError."""
    assert fetch_latest_release(f"{http_url}/latest", 5)["tag_name"] == "v1.3.0"
    with pytest.raises(OSError):
        fetch_latest_release(f"{http_url}/sin-versiones", 5)
