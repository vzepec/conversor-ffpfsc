"""Handshake ``Noise_XX_25519_ChaChaPoly_BLAKE2b`` como iniciador (Noise rev. 34).

Solo el lado cliente, que es el que usa la app. Verificado contra el vector de
cacophony que publica ps5upload (``tests/vectors/ava1/noise_xx.json``).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_BLAKE2b"
HASH_LEN = 64
DH_LEN = 32
MAC_LEN = 16


def blake2b(data: bytes) -> bytes:
    """Calcula BLAKE2b-512, la función hash de Noise.

    Args:
        data (bytes): Datos a resumir.

    Returns:
        bytes: Resumen de 64 bytes.
    """
    return hashlib.blake2b(data).digest()


def _hkdf(chaining_key: bytes, ikm: bytes) -> tuple[bytes, bytes]:
    """Deriva dos salidas con el HKDF de Noise (HMAC-BLAKE2b).

    Args:
        chaining_key (bytes): Clave de encadenamiento actual.
        ikm (bytes): Material de entrada.

    Returns:
        tuple[bytes, bytes]: Las dos salidas de 64 bytes.
    """
    temp = hmac.new(chaining_key, ikm, hashlib.blake2b).digest()
    out1 = hmac.new(temp, b"\x01", hashlib.blake2b).digest()
    out2 = hmac.new(temp, out1 + b"\x02", hashlib.blake2b).digest()
    return out1, out2


def _dh(private: X25519PrivateKey, public: bytes) -> bytes:
    """Calcula X25519 y rechaza resultados nulos (claves de orden bajo).

    Args:
        private (X25519PrivateKey): Clave privada propia.
        public (bytes): Clave pública del otro lado.

    Returns:
        bytes: Secreto compartido de 32 bytes.

    Raises:
        ValueError: Si la clave remota es de orden bajo.
    """
    shared = private.exchange(X25519PublicKey.from_public_bytes(public))
    if shared == bytes(DH_LEN):
        raise ValueError("clave remota de orden bajo")
    return shared


def public_bytes(private: X25519PrivateKey) -> bytes:
    """Obtiene la clave pública en crudo.

    Args:
        private (X25519PrivateKey): Clave privada.

    Returns:
        bytes: Clave pública de 32 bytes.
    """
    return private.public_key().public_bytes_raw()


class NoiseInitiator:
    """Estado del handshake XX del lado iniciador."""

    def __init__(
        self, static: X25519PrivateKey, prologue: bytes, ephemeral: X25519PrivateKey | None = None
    ) -> None:
        """Inicializa el estado simétrico con el nombre del protocolo y el prólogo.

        Args:
            static (X25519PrivateKey): Identidad del cliente.
            prologue (bytes): Prólogo acordado (``b"AVA1 v1"``).
            ephemeral (X25519PrivateKey | None): Efímera fija para tests; ``None`` = aleatoria.
        """
        self._s = static
        self._e = ephemeral or X25519PrivateKey.from_private_bytes(os.urandom(32))
        self._re = b""
        self.remote_static = b""
        self.h = PROTOCOL_NAME.ljust(HASH_LEN, b"\x00")
        self._ck = self.h
        self._k: bytes | None = None
        self._n = 0
        self._mix_hash(prologue)

    def write_message_1(self, payload: bytes) -> bytes:
        """Construye el mensaje 1 (``-> e``).

        Args:
            payload (bytes): Carga útil en claro.

        Returns:
            bytes: Mensaje 1.
        """
        e_pub = public_bytes(self._e)
        self._mix_hash(e_pub)
        return e_pub + self._encrypt_and_hash(payload)

    def read_message_2(self, message: bytes) -> bytes:
        """Procesa el mensaje 2 (``<- e, ee, s, es``).

        Args:
            message (bytes): Mensaje 2 recibido.

        Returns:
            bytes: Carga útil descifrada.

        Raises:
            ValueError: Si el mensaje es corto, no se puede descifrar o trae claves inválidas.
        """
        if len(message) < DH_LEN * 2 + MAC_LEN * 2:
            raise ValueError("mensaje 2 de Noise demasiado corto")
        self._re = message[:DH_LEN]
        self._mix_hash(self._re)
        self._mix_key(_dh(self._e, self._re))
        end = DH_LEN + DH_LEN + MAC_LEN
        self.remote_static = self._decrypt_and_hash(message[DH_LEN:end])
        self._mix_key(_dh(self._e, self.remote_static))
        return self._decrypt_and_hash(message[end:])

    def write_message_3(self, payload: bytes) -> bytes:
        """Construye el mensaje 3 (``-> s, se``).

        Args:
            payload (bytes): Carga útil a cifrar.

        Returns:
            bytes: Mensaje 3.
        """
        encrypted_s = self._encrypt_and_hash(public_bytes(self._s))
        self._mix_key(_dh(self._s, self._re))
        return encrypted_s + self._encrypt_and_hash(payload)

    def split(self) -> tuple[bytes, bytes]:
        """Deriva las claves de transporte tras el mensaje 3.

        Returns:
            tuple[bytes, bytes]: Claves cliente→consola y consola→cliente (32 bytes).
        """
        k1, k2 = _hkdf(self._ck, b"")
        return k1[:32], k2[:32]

    def _mix_hash(self, data: bytes) -> None:
        """Mezcla datos en el hash del handshake.

        Args:
            data (bytes): Datos a mezclar.
        """
        self.h = blake2b(self.h + data)

    def _mix_key(self, ikm: bytes) -> None:
        """Mezcla un secreto DH en la clave de encadenamiento y renueva la clave.

        Args:
            ikm (bytes): Secreto compartido.
        """
        self._ck, temp_k = _hkdf(self._ck, ikm)
        self._k, self._n = temp_k[:32], 0

    def _encrypt_and_hash(self, plaintext: bytes) -> bytes:
        """Cifra (si ya hay clave) y mezcla el resultado en el hash.

        Args:
            plaintext (bytes): Datos en claro.

        Returns:
            bytes: Datos cifrados, o en claro si aún no hay clave.
        """
        out = plaintext
        if self._k is not None:
            out = ChaCha20Poly1305(self._k).encrypt(self._nonce(), plaintext, self.h)
            self._n += 1
        self._mix_hash(out)
        return out

    def _decrypt_and_hash(self, ciphertext: bytes) -> bytes:
        """Descifra (si ya hay clave) y mezcla el texto cifrado en el hash.

        Args:
            ciphertext (bytes): Datos recibidos.

        Returns:
            bytes: Datos en claro.

        Raises:
            ValueError: Si la autenticación falla.
        """
        out = ciphertext
        if self._k is not None:
            try:
                out = ChaCha20Poly1305(self._k).decrypt(self._nonce(), ciphertext, self.h)
            except InvalidTag as exc:
                raise ValueError("mensaje de Noise alterado") from exc
            self._n += 1
        self._mix_hash(ciphertext)
        return out

    def _nonce(self) -> bytes:
        """Construye el nonce de Noise: 4 bytes cero + contador u64le.

        Returns:
            bytes: Nonce de 12 bytes.
        """
        return b"\x00" * 4 + struct.pack("<Q", self._n)
