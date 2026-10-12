"""Tests del envío de exfat2ampr.elf al cargador de ELF de la PS5."""
from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

from e2a_fake import LOCALHOST, FakeE2aEngine, FakeElfLoader
from ffpfsc_converter.infrastructure.exfat2ampr import E2aClient, send_elf


def _closed_port() -> int:
    """Devuelve un puerto local que nadie escucha."""
    with socket.socket() as probe:
        probe.bind((LOCALHOST, 0))
        return probe.getsockname()[1]


def test_send_elf_delivers_whole_file(tmp_path: Path) -> None:
    """El cargador recibe el archivo completo, byte a byte."""
    payload = os.urandom(3 * 1024 * 1024 + 17)
    elf = tmp_path / "exfat2ampr.elf"
    elf.write_bytes(payload)
    loader = FakeElfLoader()
    try:
        send_elf(loader.host, elf, port=loader.port, timeout=2)
        assert loader.wait() == payload
    finally:
        loader.stop()


def test_send_elf_missing_file(tmp_path: Path) -> None:
    """Si el ELF no existe lanza ``OSError`` sin conectarse al cargador."""
    loader = FakeElfLoader()
    try:
        with pytest.raises(OSError):
            send_elf(loader.host, tmp_path / "no-existe.elf", port=loader.port, timeout=2)
        assert loader.received == []
    finally:
        loader.stop()


def test_send_elf_loader_down(tmp_path: Path) -> None:
    """Si nadie escucha en el puerto del cargador lanza ``OSError``."""
    elf = tmp_path / "exfat2ampr.elf"
    elf.write_bytes(b"\x7fELF")
    with pytest.raises(OSError):
        send_elf(LOCALHOST, elf, port=_closed_port(), timeout=1)


def test_sending_elf_starts_fake_engine(tmp_path: Path) -> None:
    """Con el callback, enviar el ELF arranca el exfat2ampr falso (punta a punta)."""
    elf = tmp_path / "exfat2ampr.elf"
    elf.write_bytes(b"\x7fELF" + b"\x00" * 64)
    engine = FakeE2aEngine()
    loader = FakeElfLoader(on_receive=lambda _elf: engine.start())
    client = E2aClient(engine.host, port=engine.port, timeout=1)
    try:
        with pytest.raises(OSError):
            client.hello()
        send_elf(loader.host, elf, port=loader.port, timeout=2)
        loader.wait()
        assert engine.running
        assert client.hello().version == "1.45"
    finally:
        loader.stop()
        engine.stop()
