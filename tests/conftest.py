from __future__ import annotations

import json
import logging
import shutil
import struct
import threading
import zlib
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer

from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.infrastructure.ava1.codec import Decoder, Encoder


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


@pytest.fixture
def writable_ftp(ftp_root: Path) -> Iterator[int]:
    """FTP anónimo con escritura sobre la carpeta de prueba."""
    logging.getLogger("pyftpdlib").setLevel(logging.WARNING)
    auth = DummyAuthorizer()
    auth.add_anonymous(str(ftp_root), perm="elradfmw")
    server = ThreadedFTPServer(("127.0.0.1", 0), type("H", (FTPHandler,), {"authorizer": auth}))
    thread = threading.Thread(target=server.serve_forever,
                              kwargs={"timeout": 0.05, "handle_exit": False}, daemon=True)
    thread.start()
    yield server.address[1]
    server.close_all()


class FakeConsole:
    """Simula el helper: espacio libre, borrado y CRC32 reales sobre la carpeta del FTP."""

    def __init__(self, root: Path, port: int, usable: int) -> None:
        """Guarda la raíz servida, el puerto FTP y el espacio a informar."""
        self.root, self.port, self.usable = root, port, usable
        self.modes: list[bool] = []
        self.deleted: list[str] = []
        self.crc_paths: list[str] = []
        self.crc_override: dict[str, int] = {}  # ruta → CRC32 a informar (para simular daños)

    def open_session(self, host: str, ask_code: Callable[[str], str] | None = None) -> FakeConsole:
        """Devuelve el propio doble como sesión."""
        return self

    def start_ftp(self, session: object, host: str, port: int, writable: bool,
                  restart: bool) -> ConsoleTarget:
        """Registra el modo pedido y devuelve el FTP local."""
        self.modes.append(writable)
        return ConsoleTarget("127.0.0.1", self.port)

    def call(self, method: int, body: bytes) -> bytes:
        """Responde fs.freespace (44), job.run DELETE/CRC32 (20) y job.status/cancel."""
        if method == 44:
            return Encoder().u64(self.usable).u64(self.usable).u64(10**12).u64(0).u64(1).build()
        if method in (17, 18):  # job.status / job.cancel: las tareas terminan al iniciarse
            return b"" if method == 18 else self._status(body[:16], b"")
        d = Decoder(body)
        job_id, op, args = d.raw(16), d.u8(), d.blob()
        path = json.loads(args)["path"]
        if op == 4:  # CRC32
            self.crc_paths.append(path)
            local = self.root / path.lstrip("/")
            crc = self.crc_override.get(path, zlib.crc32(local.read_bytes()))
            return self._status(job_id, json.dumps({"crc32": crc, "size": 0}).encode())
        self.deleted.append(path)
        target = self.root / path.lstrip("/")
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
        return self._status(job_id, b"")

    @staticmethod
    def _status(job_id: bytes, result: bytes) -> bytes:
        """Construye un Status terminado bien, con la respuesta de la operación."""
        base = Encoder().raw(job_id).u32(1).u32(1).u64(0).u64(0).u64(0)
        status = base.u8(0).u8(0).u8(0).u8(0).build()[:-2]
        exts = [(2, b"\x01")] + ([(3, struct.pack("<I", len(result)) + result)] if result else [])
        block = struct.pack("<H", len(exts))
        for tag, data in exts:
            block += struct.pack("<HI", tag, len(data)) + data
        return status + block

    def close(self) -> None:
        """No hace nada (sesión simulada)."""
