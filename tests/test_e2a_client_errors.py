"""Tests de E2aClient ante fallos de red y respuestas que no son de exfat2ampr."""
from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from e2a_fake import LOCALHOST, FakeE2aEngine
from ffpfsc_converter.infrastructure.exfat2ampr import E2aClient, E2aHttpError


@contextmanager
def _raw_server(reply: bytes | None) -> Iterator[int]:
    """Servidor TCP de una conexión que responde ``reply`` tal cual (o nunca, si es ``None``)."""
    listener = socket.create_server((LOCALHOST, 0))
    done = threading.Event()

    def serve() -> None:
        """Atiende una conexión y la mantiene abierta hasta el final del test."""
        conn, _ = listener.accept()
        with conn:
            conn.recv(65536)
            if reply is not None:
                conn.sendall(reply)
                conn.shutdown(socket.SHUT_WR)
            done.wait(5)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield listener.getsockname()[1]
    finally:
        done.set()
        thread.join(5)
        listener.close()


def test_engine_down_raises_oserror() -> None:
    """Con el puerto sin escuchar (motor apagado) lanza ``OSError``, no ``E2aHttpError``."""
    engine = FakeE2aEngine()  # puerto reservado, sin escuchar
    try:
        with pytest.raises(OSError):
            E2aClient(engine.host, port=engine.port, timeout=1).hello()
    finally:
        engine.stop()


def test_engine_starts_later() -> None:
    """El mismo puerto responde en cuanto el motor arranca (como tras enviar el ELF)."""
    engine = FakeE2aEngine()
    client = E2aClient(engine.host, port=engine.port, timeout=1)
    try:
        with pytest.raises(OSError):
            client.hello()
        engine.start()
        assert client.hello().version == "1.45"
    finally:
        engine.stop()


def test_timeout_raises_oserror() -> None:
    """Si el motor acepta la conexión pero no responde, se agota el tiempo con ``OSError``."""
    with _raw_server(None) as port, pytest.raises(OSError):
        E2aClient(LOCALHOST, port=port, timeout=0.3).state()


def test_non_http_reply_raises_oserror() -> None:
    """Una respuesta que no es HTTP se informa como ``OSError``."""
    with _raw_server(b"esto no es HTTP\r\n") as port, pytest.raises(OSError):
        E2aClient(LOCALHOST, port=port, timeout=1).hello()


def test_invalid_json_raises_bad_response() -> None:
    """Un 200 con un cuerpo que no es JSON da ``E2aHttpError`` con código ``bad_response``."""
    reply = b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n<html>hola</html>"
    with _raw_server(reply) as port, pytest.raises(E2aHttpError) as error:
        E2aClient(LOCALHOST, port=port, timeout=1).hello()
    assert (error.value.status, error.value.code) == (200, "bad_response")


def test_unexpected_json_type_raises_bad_response() -> None:
    """Una lista donde se esperaba un objeto da ``bad_response``."""
    reply = b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n[1, 2]"
    with _raw_server(reply) as port, pytest.raises(E2aHttpError) as error:
        E2aClient(LOCALHOST, port=port, timeout=1).state()
    assert error.value.code == "bad_response"


def test_error_without_json_body() -> None:
    """Un error HTTP sin JSON conserva el código de estado."""
    reply = b"HTTP/1.0 500 Internal Server Error\r\n\r\nboom"
    with _raw_server(reply) as port, pytest.raises(E2aHttpError) as error:
        E2aClient(LOCALHOST, port=port, timeout=1).state()
    assert error.value.status == 500
