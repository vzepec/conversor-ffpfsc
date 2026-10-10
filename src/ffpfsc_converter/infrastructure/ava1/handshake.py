"""Handshake AVA1 del lado cliente (SPEC §5, pasos 1 a 4)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ffpfsc_converter.infrastructure.ava1 import keys
from ffpfsc_converter.infrastructure.ava1.codec import Decoder, Encoder
from ffpfsc_converter.infrastructure.ava1.frames import Frame, FrameConnection
from ffpfsc_converter.infrastructure.ava1.noise import NoiseInitiator

PROLOGUE = b"AVA1 v1"
PROTOCOL_VERSION = 1
TYPE_HS1, TYPE_HS2, TYPE_HS3, TYPE_WELCOME, TYPE_ERROR = 0x01, 0x02, 0x03, 0x04, 0x0B
_EXT_NAME = 1


class Ava1Refused(ConnectionError):
    """La consola rechazó la operación con un código ``ERR_*``.

    Attributes:
        code (int): Código de error AVA1 (por ejemplo, 2 = ventana de emparejamiento cerrada).
        reason (str): Causa informada por la consola.
    """

    def __init__(self, code: int, reason: str) -> None:
        """Crea el error.

        Args:
            code (int): Código ``ERR_*``.
            reason (str): Causa informada por la consola.
        """
        super().__init__(f"AVA1 error {code}: {reason}")
        self.code = code
        self.reason = reason


class WrongConsoleError(ConnectionError):
    """La clave de la consola no coincide con la emparejada en esa dirección."""


@dataclass(frozen=True)
class Established:
    """Resultado de un handshake correcto.

    Attributes:
        handshake_hash (bytes): Hash ``h`` de Noise (64 bytes), base del emparejamiento.
        server_key (bytes): Clave estática de la consola.
        server_name (str): Nombre que informa la consola.
        needs_code (bool): ``True`` si la consola aún no conoce a la app (pide código).
        caps (int): Capacidades anunciadas (bit 1 = métodos de gestión).
    """

    handshake_hash: bytes
    server_key: bytes
    server_name: str
    needs_code: bool
    caps: int


def raise_if_error(frame: Frame) -> None:
    """Convierte una trama ``Error`` en excepción.

    Args:
        frame (Frame): Trama recibida.

    Raises:
        Ava1Refused: Si la trama es de tipo ``Error``.
    """
    if frame.ty == TYPE_ERROR:
        d = Decoder(frame.body)
        raise Ava1Refused(d.u16(), d.text())


def client_handshake(
    conn: FrameConnection,
    identity: X25519PrivateKey,
    client_name: str,
    expected_key: bytes | None,
) -> Established:
    """Ejecuta el handshake Noise XX y valida el ``Welcome`` de la consola.

    Args:
        conn (FrameConnection): Conexión recién abierta, sin claves.
        identity (X25519PrivateKey): Identidad estática de la app.
        client_name (str): Nombre con el que se presenta la app.
        expected_key (bytes | None): Clave de la consola si ya se emparejó con esta dirección.

    Returns:
        Established: Datos de la sesión; el canal queda sellado.

    Raises:
        Ava1Refused: Si la consola rechaza la conexión.
        WrongConsoleError: Si la consola no es la emparejada.
        ConnectionError: Si una respuesta no respeta el protocolo.
    """
    noise = NoiseInitiator(identity, PROLOGUE)
    hello = Encoder().u16(PROTOCOL_VERSION).u16(PROTOCOL_VERSION).u64(0).build()
    conn.send(TYPE_HS1, 0, Encoder().blob(noise.write_message_1(hello)).build())

    frame = _expect(conn, TYPE_HS2)
    info = Decoder(noise.read_message_2(_noise_payload(frame)))
    version, caps = info.u16(), info.u64()
    _session_id, commit = info.raw(16), info.raw(32)
    name = _ext_text(info.extensions(), _EXT_NAME)
    if version != PROTOCOL_VERSION:
        raise ConnectionError(f"versión de AVA1 no soportada: {version}")
    if expected_key is not None and not keys.same(noise.remote_static, expected_key):
        raise WrongConsoleError("la consola no es la que se emparejó en esta dirección")

    client_info = Encoder().raw(os.urandom(16)).ext_str(_EXT_NAME, client_name).build()
    conn.send(TYPE_HS3, 0, Encoder().blob(noise.write_message_3(client_info)).build())
    c2s, s2c = noise.split()
    conn.set_keys(keys.control_key(c2s), keys.control_key(s2c))

    welcome = Decoder(_expect(conn, TYPE_WELCOME).body)
    knows_you, nonce_s = welcome.u8(), welcome.raw(16)
    welcome.extensions()
    if not keys.same(keys.pair_commit(nonce_s), commit):
        raise ConnectionError("compromiso de emparejamiento inválido")
    return Established(noise.h, noise.remote_static, name, knows_you == 0, caps)


def _expect(conn: FrameConnection, ty: int) -> Frame:
    """Recibe una trama y comprueba su tipo.

    Args:
        conn (FrameConnection): Conexión.
        ty (int): Tipo esperado.

    Returns:
        Frame: Trama recibida.

    Raises:
        Ava1Refused: Si llega un ``Error``.
        ConnectionError: Si llega otro tipo.
    """
    frame = conn.recv()
    raise_if_error(frame)
    if frame.ty != ty:
        raise ConnectionError(f"trama AVA1 inesperada: {frame.ty:#x}")
    return frame


def _noise_payload(frame: Frame) -> bytes:
    """Extrae el mensaje Noise de una trama ``Hs*``.

    Args:
        frame (Frame): Trama de handshake.

    Returns:
        bytes: Mensaje Noise.
    """
    d = Decoder(frame.body)
    message = d.blob()
    d.extensions()
    return message


def _ext_text(extensions: dict[int, bytes], tag: int) -> str:
    """Lee una extensión de texto, si existe.

    Args:
        extensions (dict[int, bytes]): Extensiones decodificadas.
        tag (int): Etiqueta buscada.

    Returns:
        str: Texto de la extensión, o cadena vacía.
    """
    raw = extensions.get(tag)
    return Decoder(raw).text() if raw else ""
