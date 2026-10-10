"""Tramas AVA1 sobre TCP: cabecera con CRC32C y sellado ChaCha20-Poly1305 (SPEC §2, §4.4)."""
from __future__ import annotations

import socket
import struct
import threading
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

MAGIC = b"A1"
HEADER_LEN = 16
MAC_LEN = 16
FLAG_SEALED = 0x01
#: Límite de cuerpo que aceptamos (respuestas RPC de hasta 256 KiB + margen).
MAX_BODY = 256 * 1024 + 1024


def _crc32c_table() -> list[int]:
    """Calcula la tabla de CRC32C (Castagnoli, reflejado).

    Returns:
        list[int]: 256 entradas.
    """
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0x82F63B78 if c & 1 else c >> 1
        table.append(c)
    return table


_TABLE = _crc32c_table()


def crc32c(data: bytes) -> int:
    """Calcula el CRC32C de unos bytes.

    Args:
        data (bytes): Datos a resumir.

    Returns:
        int: CRC de 32 bits.
    """
    crc = 0xFFFFFFFF
    for byte in data:
        crc = _TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def encode_header(ty: int, flags: int, channel: int, body_len: int) -> bytes:
    """Construye la cabecera de 16 bytes de una trama.

    Args:
        ty (int): Tipo de mensaje.
        flags (int): Banderas (bit 0 = sellada).
        channel (int): Canal (id de petición en RPC).
        body_len (int): Longitud del cuerpo tal como viaja.

    Returns:
        bytes: Cabecera con su CRC32C.
    """
    head = MAGIC + struct.pack("<BBII", ty, flags, channel, body_len)
    return head + struct.pack("<I", crc32c(head))


@dataclass(frozen=True)
class Frame:
    """Trama recibida y ya abierta.

    Attributes:
        ty (int): Tipo de mensaje.
        channel (int): Canal.
        body (bytes): Cuerpo en claro.
    """

    ty: int
    channel: int
    body: bytes


class FrameConnection:
    """Envía y recibe tramas; tras el handshake las sella con contadores por sentido."""

    def __init__(self, sock: socket.socket) -> None:
        """Envuelve un socket ya conectado.

        Args:
            sock (socket.socket): Conexión TCP con la consola.
        """
        self._sock = sock
        self._send_key: ChaCha20Poly1305 | None = None
        self._recv_key: ChaCha20Poly1305 | None = None
        self._send_ctr = 0
        self._recv_ctr = 0
        self._send_lock = threading.Lock()

    def set_keys(self, send_key: bytes, recv_key: bytes) -> None:
        """Activa el sellado con las claves del canal de control.

        Args:
            send_key (bytes): Clave cliente → consola (32 bytes).
            recv_key (bytes): Clave consola → cliente (32 bytes).
        """
        self._send_key, self._recv_key = ChaCha20Poly1305(send_key), ChaCha20Poly1305(recv_key)
        self._send_ctr = self._recv_ctr = 0

    def send(self, ty: int, channel: int, body: bytes) -> None:
        """Envía una trama, sellada si ya hay claves (seguro entre hilos).

        Args:
            ty (int): Tipo de mensaje.
            channel (int): Canal.
            body (bytes): Cuerpo en claro.

        Raises:
            OSError: Si falla el envío.
        """
        with self._send_lock:
            if self._send_key is None:
                self._sock.sendall(encode_header(ty, 0, channel, len(body)) + body)
                return
            header = encode_header(ty, FLAG_SEALED, channel, len(body) + MAC_LEN)
            sealed = self._send_key.encrypt(_nonce(self._send_ctr), body, header[:12])
            self._send_ctr += 1
            self._sock.sendall(header + sealed)

    def recv(self) -> Frame:
        """Recibe la siguiente trama y la abre si viene sellada.

        Returns:
            Frame: Trama en claro.

        Raises:
            ConnectionError: Si la trama es inválida o no se puede abrir.
            OSError: Si se corta la conexión.
        """
        header = self._read_exact(HEADER_LEN)
        if header[:2] != MAGIC or struct.unpack("<I", header[12:])[0] != crc32c(header[:12]):
            raise ConnectionError("trama AVA1 inválida")
        ty, flags, channel, body_len = struct.unpack("<BBII", header[2:12])
        if body_len > MAX_BODY:
            raise ConnectionError("trama AVA1 demasiado grande")
        body = self._read_exact(body_len)
        if self._recv_key is not None:
            if not flags & FLAG_SEALED:
                raise ConnectionError("trama AVA1 sin sellar tras el handshake")
            try:
                body = self._recv_key.decrypt(_nonce(self._recv_ctr), body, header[:12])
            except InvalidTag as exc:
                raise ConnectionError("trama AVA1 alterada") from exc
            self._recv_ctr += 1
        return Frame(ty, channel, body)

    def _read_exact(self, size: int) -> bytes:
        """Lee exactamente ``size`` bytes del socket.

        Args:
            size (int): Bytes a leer.

        Returns:
            bytes: Datos leídos.

        Raises:
            ConnectionError: Si la consola cierra la conexión antes.
        """
        chunks, remaining = [], size
        while remaining:
            chunk = self._sock.recv(remaining)
            if not chunk:
                raise ConnectionError("la PS5 cerró la conexión AVA1")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


def _nonce(counter: int) -> bytes:
    """Construye el nonce AEAD de una trama: 4 bytes cero + contador u64le.

    Args:
        counter (int): Contador de tramas de ese sentido.

    Returns:
        bytes: Nonce de 12 bytes.
    """
    return b"\x00" * 4 + struct.pack("<Q", counter)
