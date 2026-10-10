from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer


@pytest.fixture
def game_folder(tmp_path: Path) -> Path:
    """Carpeta de juego mínima: ``Juego/PPSA00000-app/{eboot.bin, sce_sys/param.json}``."""
    root = tmp_path / "Juego" / "PPSA00000-app"
    (root / "sce_sys").mkdir(parents=True)
    (root / "eboot.bin").write_bytes(b"\x00" * 1024)
    (root / "sce_sys" / "param.json").write_text(json.dumps({
        "titleId": "PPSA00000",
        "contentVersion": "01.000.000",
        "localizedParameters": {
            "defaultLanguage": "en-US",
            "en-US": {"titleName": "Test Game"},
        },
    }))
    return tmp_path / "Juego"


@pytest.fixture
def ftp_root(tmp_path: Path) -> Path:
    """Carpeta que sirve el FTP de prueba, con estructura parecida a la PS5."""
    root = tmp_path / "ps5"
    game = root / "data" / "homebrew" / "Juego"
    (game / "sce_sys").mkdir(parents=True)
    (game / "eboot.bin").write_bytes(b"E" * 300_000)
    (game / "sce_sys" / "param.json").write_text('{"titleId": "PPSA00000"}')
    (game / "vacia").mkdir()
    (root / "data" / "homebrew" / "imagen.ffpfsc").write_bytes(b"F" * 50_000)
    return root


@pytest.fixture
def ftp_server(ftp_root: Path) -> Iterator[int]:
    """Servidor FTP anónimo de solo lectura en localhost; devuelve su puerto."""
    logging.getLogger("pyftpdlib").setLevel(logging.WARNING)
    authorizer = DummyAuthorizer()
    authorizer.add_anonymous(str(ftp_root), perm="elr")
    handler = type("Handler", (FTPHandler,), {"authorizer": authorizer})
    server = ThreadedFTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever,
                              kwargs={"timeout": 0.05, "handle_exit": False}, daemon=True)
    thread.start()
    yield server.address[1]
    server.close_all()
    thread.join(timeout=5)
