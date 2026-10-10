"""Derivaciones de claves de AVA1 y PAKE de emparejamiento (SPEC §4.3, §4.6).

El mapa Elligator2 es el de RFC 9380 (``map_to_curve_elligator2_curve25519``,
Z = 2), la misma función que usan Monocypher y ps5upload. ``tests/vectors/ava1``
fija toda la cadena byte a byte.
"""
from __future__ import annotations

import hashlib
import hmac

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

_P = 2**255 - 19
_A = 486662
_HIDDEN_MASK = (1 << 254) - 1


def _b2b256(*parts: bytes, key: bytes = b"") -> bytes:
    """Calcula BLAKE2b-256 (con clave opcional) sobre la concatenación de partes.

    Args:
        *parts (bytes): Datos a resumir, en orden.
        key (bytes): Clave para el modo con clave; vacía = sin clave.

    Returns:
        bytes: Resumen de 32 bytes.
    """
    return hashlib.blake2b(b"".join(parts), digest_size=32, key=key).digest()


def control_key(direction_key: bytes) -> bytes:
    """Deriva la clave del canal de control (carril 0) para un sentido.

    Args:
        direction_key (bytes): Clave de ese sentido obtenida del ``split`` de Noise.

    Returns:
        bytes: Clave ChaCha20-Poly1305 de 32 bytes.
    """
    return lane_key(direction_key, 0, bytes(16), bytes(16))


def lane_key(direction_key: bytes, lane: int, client_nonce: bytes, server_nonce: bytes) -> bytes:
    """Deriva la clave de un carril: BLAKE2b-256(key=dir, "AVA1 lane" ‖ u16le(n) ‖ cn ‖ sn).

    Args:
        direction_key (bytes): Clave de sentido de Noise.
        lane (int): Número de carril.
        client_nonce (bytes): Nonce del cliente (16 bytes).
        server_nonce (bytes): Nonce de la consola (16 bytes).

    Returns:
        bytes: Clave de 32 bytes.
    """
    return _b2b256(b"AVA1 lane", lane.to_bytes(2, "little"), client_nonce, server_nonce,
                   key=direction_key)


def pair_commit(nonce_s: bytes) -> bytes:
    """Calcula el compromiso de emparejamiento: BLAKE2b-256(nonce_s).

    Args:
        nonce_s (bytes): Nonce revelado por la consola en ``Welcome``.

    Returns:
        bytes: Compromiso de 32 bytes.
    """
    return _b2b256(nonce_s)


def elligator_map(hidden: bytes) -> bytes:
    """Aplica Elligator2 de Curve25519 (coordenada u), ignorando los 2 bits superiores.

    Args:
        hidden (bytes): 32 bytes uniformes.

    Returns:
        bytes: Punto u de 32 bytes, little-endian.
    """
    r = int.from_bytes(hidden, "little") & _HIDDEN_MASK
    w = (-_A * pow((1 + 2 * r * r) % _P, _P - 2, _P)) % _P
    gw = w * (w * w + _A * w + 1) % _P
    is_square = gw != 0 and pow(gw, (_P - 1) // 2, _P) == 1
    u = w if is_square else (-w - _A) % _P
    return u.to_bytes(32, "little")


def generator(handshake_hash: bytes, code: str) -> bytes:
    """Calcula el generador CPace a partir del hash del handshake y el código.

    Args:
        handshake_hash (bytes): Hash ``h`` de Noise (64 bytes).
        code (str): Código de seis dígitos que muestra la PS5.

    Returns:
        bytes: Generador ``G`` de 32 bytes.
    """
    return elligator_map(_b2b256(b"AVA1 CPace", handshake_hash, code.encode("ascii")))


def x25519(scalar: bytes, point: bytes) -> bytes:
    """Multiplica un punto por un escalar (X25519) y rechaza el resultado nulo.

    Args:
        scalar (bytes): Escalar de 32 bytes (se recorta según X25519).
        point (bytes): Coordenada u de 32 bytes.

    Returns:
        bytes: Resultado de 32 bytes.

    Raises:
        ValueError: Si el resultado es el punto nulo (valor degenerado).
    """
    try:
        out = X25519PrivateKey.from_private_bytes(scalar).exchange(
            X25519PublicKey.from_public_bytes(point))
    except ValueError as exc:
        raise ValueError("valor de emparejamiento degenerado") from exc
    if out == bytes(32):
        raise ValueError("valor de emparejamiento degenerado")
    return out


def pake_key(handshake_hash: bytes, scalar: bytes, y_peer: bytes, y_client: bytes,
             y_server: bytes) -> bytes:
    """Deriva la clave de emparejamiento ``K``.

    Args:
        handshake_hash (bytes): Hash ``h`` de Noise.
        scalar (bytes): Escalar secreto propio.
        y_peer (bytes): Valor público del otro lado.
        y_client (bytes): Valor público del cliente.
        y_server (bytes): Valor público de la consola.

    Returns:
        bytes: Clave ``K`` de 32 bytes.

    Raises:
        ValueError: Si el valor del otro lado es degenerado.
    """
    shared = x25519(scalar, y_peer)
    return _b2b256(b"AVA1 CPace K", handshake_hash, shared, y_client, y_server)


def pake_mac(key: bytes, role: bytes, handshake_hash: bytes) -> bytes:
    """Calcula la confirmación de clave de un rol (``b"client"`` o ``b"server"``).

    Args:
        key (bytes): Clave ``K``.
        role (bytes): Rol que confirma.
        handshake_hash (bytes): Hash ``h`` de Noise.

    Returns:
        bytes: MAC de 32 bytes.
    """
    return _b2b256(role, handshake_hash, key=key)


def same(a: bytes, b: bytes) -> bool:
    """Compara dos valores en tiempo constante.

    Args:
        a (bytes): Primer valor.
        b (bytes): Segundo valor.

    Returns:
        bool: ``True`` si son iguales.
    """
    return hmac.compare_digest(a, b)
