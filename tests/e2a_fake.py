"""exfat2ampr falso por HTTP y cargador de ELF falso, para tests de punta a punta.

Uso típico::

    engine = FakeE2aEngine()          # reserva un puerto en 127.0.0.1 (aún rechaza conexiones)
    engine.start()                    # empieza a responder como exfat2ampr 1.45
    client = E2aClient(engine.host, engine.issue_token(), port=engine.port, timeout=2)
    ...
    engine.advance(50); engine.finish("done")
    engine.stop()

Mientras no se llama a ``start()`` el puerto está reservado pero sin escuchar, así
que el cliente recibe "conexión rechazada" como con el motor apagado. Con
``FakeElfLoader(on_receive=lambda _elf: engine.start())`` se simula que enviar el
ELF arranca el motor.
"""
from __future__ import annotations

import json
import socketserver
import threading
import urllib.parse
from collections.abc import Callable, Iterable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from e2a_fake_data import FakeDestination, FakeGame, FakeRequest
from e2a_fake_logic import FakeE2aLogic
from ffpfsc_converter.infrastructure.exfat2ampr.transport import TOKEN_HEADER

LOCALHOST = "127.0.0.1"
_POLL_INTERVAL = 0.05


class _HttpServer(ThreadingHTTPServer):
    """Servidor HTTP que conoce el motor falso al que reparte las peticiones."""

    daemon_threads = True
    engine: FakeE2aLogic


class _Handler(BaseHTTPRequestHandler):
    """Traduce cada petición HTTP/1.0 a una :class:`FakeRequest` y responde JSON."""

    server: _HttpServer

    def do_GET(self) -> None:
        """Atiende un ``GET``."""
        self._serve("GET")

    def do_POST(self) -> None:
        """Atiende un ``POST``."""
        self._serve("POST")

    def log_message(self, format: str, *args: object) -> None:
        """Silencia el registro de cada petición en la salida de los tests."""

    def _serve(self, method: str) -> None:
        """Lee parámetros (cuerpo o *query*) y token, y envía la respuesta del motor."""
        url = urllib.parse.urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        query = dict(urllib.parse.parse_qsl(url.query, keep_blank_values=True))
        params = dict(urllib.parse.parse_qsl(body, keep_blank_values=True)) if body else query
        token = self.headers.get(TOKEN_HEADER) or query.get("t")
        reply = self.server.engine.handle(FakeRequest(method, url.path, params, token))
        data = json.dumps(reply.body).encode("utf-8")
        self.send_response(reply.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class FakeE2aEngine(FakeE2aLogic):
    """exfat2ampr falso que escucha en ``127.0.0.1`` (puerto libre elegido por el sistema).

    Attributes:
        host (str): ``"127.0.0.1"``.
        port (int): Puerto reservado (válido desde el constructor).
    """

    def __init__(self, pin: str = "123456", games: Iterable[FakeGame] | None = None,
                 destinations: Iterable[FakeDestination] | None = None) -> None:
        """Reserva el puerto sin escuchar todavía (ver :meth:`start`)."""
        super().__init__(pin, games, destinations)
        self._server = _HttpServer((LOCALHOST, 0), _Handler, bind_and_activate=False)
        self._server.engine = self
        self._server.server_bind()
        self.host = LOCALHOST
        self.port: int = self._server.server_address[1]
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        """Indica si ya responde peticiones.

        Returns:
            bool: ``True`` tras :meth:`start`.
        """
        return self._thread is not None

    def start(self) -> FakeE2aEngine:
        """Empieza a escuchar y responder en un hilo *daemon* (idempotente).

        Returns:
            FakeE2aEngine: El mismo motor, para encadenar.
        """
        with self.lock:
            if self._thread is None:
                self._server.server_activate()
                self._thread = threading.Thread(
                    target=self._server.serve_forever, args=(_POLL_INTERVAL,), daemon=True)
                self._thread.start()
        return self

    def stop(self) -> None:
        """Deja de responder y libera el puerto."""
        if self._thread is not None:
            self._server.shutdown()
            self._thread.join()
        self._server.server_close()


class _ElfServer(socketserver.ThreadingTCPServer):
    """Servidor TCP que conoce el cargador falso al que entrega lo recibido."""

    daemon_threads = True
    allow_reuse_address = True
    loader: FakeElfLoader


class _ElfHandler(socketserver.BaseRequestHandler):
    """Lee el ELF completo hasta que el cliente cierra la conexión."""

    server: _ElfServer

    def handle(self) -> None:
        """Recibe el binario y lo entrega al cargador falso."""
        self.request.settimeout(5)
        chunks = []
        while chunk := self.request.recv(64 * 1024):
            chunks.append(chunk)
        self.server.loader.deliver(b"".join(chunks))


class FakeElfLoader:
    """Cargador de ELF falso (como etaHEN en el puerto 9021) en ``127.0.0.1``.

    Attributes:
        host (str): ``"127.0.0.1"``.
        port (int): Puerto donde escucha.
        received (list[bytes]): Binarios recibidos, en orden.
    """

    def __init__(self, on_receive: Callable[[bytes], None] | None = None) -> None:
        """Empieza a escuchar en un hilo *daemon*.

        Args:
            on_receive (Callable[[bytes], None] | None): Se llama con cada ELF recibido
                (por ejemplo, para arrancar un :class:`FakeE2aEngine`).
        """
        self.on_receive = on_receive
        self.received: list[bytes] = []
        self._got = threading.Event()
        self._server = _ElfServer((LOCALHOST, 0), _ElfHandler)
        self._server.loader = self
        self.host = LOCALHOST
        self.port: int = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, args=(_POLL_INTERVAL,), daemon=True)
        self._thread.start()

    def deliver(self, elf: bytes) -> None:
        """Guarda un ELF recibido y avisa al *callback*."""
        self.received.append(elf)
        if self.on_receive is not None:
            self.on_receive(elf)
        self._got.set()

    def wait(self, timeout: float = 2.0) -> bytes:
        """Espera a que llegue un ELF.

        Returns:
            bytes: El último ELF recibido.
        """
        assert self._got.wait(timeout), "el cargador falso no recibió ningún ELF"
        return self.received[-1]

    def stop(self) -> None:
        """Deja de escuchar y libera el puerto."""
        self._server.shutdown()
        self._thread.join()
        self._server.server_close()
