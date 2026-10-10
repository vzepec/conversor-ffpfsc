"""Sesión AVA1 con el helper de ps5upload: emparejamiento y llamadas RPC.

Tras el handshake, un hilo lector responde los ``Ping`` de la consola (que
corta las conexiones mudas a los 12 s) y entrega las respuestas por canal.
"""
from __future__ import annotations

import json
import os
import queue
import socket
import threading
from typing import Any

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ffpfsc_converter.infrastructure.ava1 import keys
from ffpfsc_converter.infrastructure.ava1.codec import Decoder, Encoder
from ffpfsc_converter.infrastructure.ava1.frames import Frame, FrameConnection
from ffpfsc_converter.infrastructure.ava1.handshake import (
    TYPE_ERROR,
    Ava1Refused,
    Established,
    client_handshake,
)

TYPE_PAIR_CONFIRM, TYPE_PAIR_RESULT, TYPE_PING, TYPE_PONG = 0x05, 0x06, 0x09, 0x0A
TYPE_BYE, TYPE_PAKE_CLIENT, TYPE_PAKE_SERVER = 0x0C, 0x0D, 0x0E
TYPE_RPC_REQUEST, TYPE_RPC_RESPONSE = 0x60, 0x61
METHOD_FTP_START = 119
ERR_PAIRING_CODE = 19
_REPLY_TYPES = frozenset({TYPE_PAIR_RESULT, TYPE_PAKE_SERVER, TYPE_RPC_RESPONSE})
_REPLY_TIMEOUT = 20.0


class Ava1Session:
    """Conexión de control con el helper de ps5upload."""

    def __init__(self, host: str, port: int, timeout: float) -> None:
        """Abre la conexión TCP (sin handshake todavía).

        Args:
            host (str): Dirección de la PS5.
            port (int): Puerto AVA1 (9120).
            timeout (float): Segundos de espera de red.

        Raises:
            OSError: Si la PS5 no acepta la conexión.
        """
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._conn = FrameConnection(self._sock)
        self._replies: dict[int, queue.Queue[Frame | Exception]] = {}
        self._lock = threading.Lock()
        self._next_id = 1
        self._closed = threading.Event()
        self.established: Established | None = None

    def handshake(
        self, identity: X25519PrivateKey, name: str, expected: bytes | None
    ) -> Established:
        """Ejecuta el handshake y arranca el hilo lector.

        Args:
            identity (X25519PrivateKey): Identidad de la app.
            name (str): Nombre con el que se presenta la app.
            expected (bytes | None): Clave esperada de la consola, si ya se emparejó.

        Returns:
            Established: Datos de la sesión.

        Raises:
            ConnectionError: Si el handshake falla o la consola lo rechaza.
        """
        self.established = client_handshake(self._conn, identity, name, expected)
        # El lector espera sin límite: los Ping de la consola mantienen vivo el enlace.
        self._sock.settimeout(None)
        threading.Thread(target=self._read_loop, daemon=True).start()
        return self.established

    def pair(self, code: str) -> None:
        """Confirma el emparejamiento con el código que muestra la PS5 (PAKE CPace).

        Args:
            code (str): Código de seis dígitos.

        Raises:
            Ava1Refused: Si la consola rechaza el código (``ERR_PAIRING_CODE``).
            ConnectionError: Si se pierde la conexión.
        """
        h = self._hash()
        scalar = os.urandom(32)
        y_client = keys.x25519(scalar, keys.generator(h, code))
        reply = self._request(TYPE_PAKE_CLIENT, Encoder().raw(y_client).build())
        y_server = Decoder(reply.body).raw(32)
        key = keys.pake_key(h, scalar, y_server, y_client, y_server)
        reply = self._request(TYPE_PAIR_CONFIRM,
                              Encoder().raw(keys.pake_mac(key, b"client", h)).build())
        result = Decoder(reply.body)
        accepted, server_mac = result.u8(), result.raw(32)
        if not accepted:
            raise Ava1Refused(ERR_PAIRING_CODE, "la PS5 no aceptó el código")
        if not keys.same(server_mac, keys.pake_mac(key, b"server", h)):
            raise Ava1Refused(ERR_PAIRING_CODE, "la PS5 no pudo demostrar que conoce el código")

    def call(self, method: int, body: bytes) -> bytes:
        """Llama a un método RPC y devuelve el cuerpo de la respuesta.

        Args:
            method (int): Número de método AVA1.
            body (bytes): Cuerpo de la petición ya codificado.

        Returns:
            bytes: Cuerpo de la respuesta (estado OK).

        Raises:
            Ava1Refused: Si la consola responde con un estado de error.
            ConnectionError: Si se pierde la conexión.
        """
        request = Encoder().u16(method).blob(body).build()
        reply = Decoder(self._request(TYPE_RPC_REQUEST, request).body)
        status, data = reply.u16(), reply.blob()
        if status != 0:
            raise Ava1Refused(status, data.decode("utf-8", "replace"))
        return data

    def call_text(self, method: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Llama a un método de gestión cuyo cuerpo es JSON (``MgmtText``).

        Args:
            method (int): Número de método (por ejemplo, 119 = ``ftp.start``).
            payload (dict[str, Any]): Petición JSON.

        Returns:
            dict[str, Any]: Respuesta JSON de la consola.

        Raises:
            Ava1Refused: Si la consola responde con un estado de error.
            ConnectionError: Si se pierde la conexión.
        """
        body = Encoder().blob(json.dumps(payload).encode()).build()
        return json.loads(Decoder(self.call(method, body)).blob().decode("utf-8"))

    def close(self) -> None:
        """Envía ``Bye`` y cierra la conexión."""
        if self._closed.is_set():
            return
        try:
            if self.established is not None:
                self._conn.send(TYPE_BYE, 0, Encoder().u8(0).build())
        except OSError:
            pass
        self._closed.set()
        self._sock.close()

    def _hash(self) -> bytes:
        """Obtiene el hash del handshake.

        Returns:
            bytes: Hash ``h`` de Noise.

        Raises:
            ConnectionError: Si aún no se hizo el handshake.
        """
        if self.established is None:
            raise ConnectionError("handshake AVA1 pendiente")
        return self.established.handshake_hash

    def _request(self, ty: int, body: bytes) -> Frame:
        """Envía una petición y espera la respuesta en su canal.

        Args:
            ty (int): Tipo de la trama de petición.
            body (bytes): Cuerpo de la petición.

        Returns:
            Frame: Trama de respuesta.

        Raises:
            ConnectionError: Si la consola corta, responde con ``Error`` o no responde a tiempo.
        """
        with self._lock:
            channel, self._next_id = self._next_id, self._next_id + 1
            waiter: queue.Queue[Frame | Exception] = queue.Queue(maxsize=1)
            self._replies[channel] = waiter
        self._conn.send(ty, channel, body)
        try:
            reply = waiter.get(timeout=_REPLY_TIMEOUT)
        except queue.Empty as exc:
            raise ConnectionError("la PS5 no respondió a tiempo") from exc
        if isinstance(reply, Exception):
            raise reply
        return reply

    def _read_loop(self) -> None:
        """Lee tramas: responde Ping, entrega respuestas y propaga los errores."""
        failure: Exception = ConnectionError("la PS5 cerró la conexión AVA1")
        try:
            while not self._closed.is_set():
                frame = self._conn.recv()
                if frame.ty == TYPE_PING:
                    self._conn.send(TYPE_PONG, frame.channel, frame.body)
                elif frame.ty in _REPLY_TYPES:
                    waiter = self._replies.pop(frame.channel, None)
                    if waiter is not None:
                        waiter.put(frame)
                elif frame.ty == TYPE_ERROR:
                    d = Decoder(frame.body)
                    failure = Ava1Refused(d.u16(), d.text())
                    break
                elif frame.ty == TYPE_BYE:
                    break
        except (OSError, ValueError) as exc:
            failure = exc if isinstance(exc, ConnectionError) else ConnectionError(str(exc))
        for waiter in list(self._replies.values()):
            waiter.put(failure)
        self._replies.clear()
