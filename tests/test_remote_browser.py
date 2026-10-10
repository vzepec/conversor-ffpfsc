from __future__ import annotations

import io
import socket
from pathlib import Path

from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.domain.remote_events import (
    RemoteConnected,
    RemoteDisconnected,
    RemoteError,
    RemoteListing,
)
from ffpfsc_converter.infrastructure.ftp import FtpClient
from ffpfsc_converter.services.remote_browser import RemoteBrowser


def _free_port() -> int:
    """Obtiene un puerto local donde no escucha nadie."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_client_lists_walks_and_resumes(ftp_server: int) -> None:
    """El cliente lista, recorre y descarga desde un desplazamiento."""
    client = FtpClient(ConsoleTarget("127.0.0.1", ftp_server))
    client.connect()
    try:
        names = [e.name for e in client.list_dir("/data/homebrew")]
        assert names == ["Juego", "imagen.ffpfsc"]
        walked = sorted(e.path for e in client.walk("/data/homebrew/Juego"))
        assert "/data/homebrew/Juego/sce_sys/param.json" in walked
        assert "/data/homebrew/Juego/vacia" in walked
        sink = io.BytesIO()
        chunks: list[int] = []
        client.download("/data/homebrew/imagen.ffpfsc", sink, 10_000, chunks.append)
        assert len(sink.getvalue()) == 40_000 == sum(chunks)
    finally:
        client.close()
    assert not client.is_connected


def test_browser_connects_and_opens_start_folder(ftp_server: int) -> None:
    """Al conectar abre /data/homebrew y luego navega donde se le pide."""
    events: list[object] = []
    browser = RemoteBrowser(events.append)
    browser.connect(ConsoleTarget("127.0.0.1", ftp_server))
    browser.open("/data")
    browser.wait_idle()
    assert isinstance(events[0], RemoteConnected)
    assert events[1] == RemoteListing("/data/homebrew", events[1].entries)
    assert [e.name for e in events[2].entries] == ["homebrew"]
    assert browser.is_connected
    browser.disconnect()
    browser.wait_idle()
    assert isinstance(events[-1], RemoteDisconnected)


def test_browser_falls_back_to_root(ftp_server: int, ftp_root: Path) -> None:
    """Si la carpeta inicial no existe, abre la raíz."""
    (ftp_root / "data" / "homebrew").rename(ftp_root / "data" / "otra")
    events: list[object] = []
    browser = RemoteBrowser(events.append)
    browser.connect(ConsoleTarget("127.0.0.1", ftp_server))
    browser.wait_idle()
    assert events[1].path == "/"


def test_browser_reports_missing_folder(ftp_server: int) -> None:
    """Una carpeta inexistente da error pero mantiene la conexión."""
    events: list[object] = []
    browser = RemoteBrowser(events.append)
    browser.connect(ConsoleTarget("127.0.0.1", ftp_server))
    browser.open("/no/existe")
    browser.wait_idle()
    assert isinstance(events[-1], RemoteError)
    assert "no permitió abrir /no/existe" in events[-1].message
    assert browser.is_connected


def test_refused_connection_explains_how_to_start_ftp() -> None:
    """Si el FTP no está iniciado, el mensaje indica cómo hacerlo en ps5upload."""
    events: list[object] = []
    browser = RemoteBrowser(events.append)
    browser.connect(ConsoleTarget("127.0.0.1", _free_port()))
    browser.wait_idle()
    assert len(events) == 1 and isinstance(events[0], RemoteError)
    assert "FTP Server → Start" in events[0].message
    assert not browser.is_connected


def test_open_without_connection_is_reported() -> None:
    """Abrir una carpeta sin conexión publica un error claro."""
    events: list[object] = []
    browser = RemoteBrowser(events.append)
    browser.open("/data")
    browser.wait_idle()
    assert isinstance(events[0], RemoteError) and "Conectar" in events[0].message
