"""Codificación de mensajes AVA1 (SPEC §3).

Un cuerpo son los campos fijos en orden (enteros little-endian, ``b16``/``b32``
en crudo, ``bytes`` = u32 + datos, ``str`` = u16 + UTF-8) seguidos de un bloque
de extensiones: u16 cantidad y, por cada una, u16 etiqueta, u32 longitud y valor.
"""
from __future__ import annotations

import struct


class DecodeError(ValueError):
    """El cuerpo recibido no respeta el formato AVA1."""


class Encoder:
    """Construye un cuerpo AVA1 campo a campo."""

    def __init__(self) -> None:
        """Crea un cuerpo vacío."""
        self._parts: list[bytes] = []
        self._ext: list[tuple[int, bytes]] = []

    def u8(self, value: int) -> Encoder:
        """Agrega un entero sin signo de 8 bits.

        Args:
            value (int): Valor entre 0 y 255.

        Returns:
            Encoder: El mismo codificador, para encadenar.
        """
        self._parts.append(struct.pack("<B", value))
        return self

    def u16(self, value: int) -> Encoder:
        """Agrega un entero sin signo de 16 bits.

        Args:
            value (int): Valor a codificar.

        Returns:
            Encoder: El mismo codificador, para encadenar.
        """
        self._parts.append(struct.pack("<H", value))
        return self

    def u32(self, value: int) -> Encoder:
        """Agrega un entero sin signo de 32 bits.

        Args:
            value (int): Valor a codificar.

        Returns:
            Encoder: El mismo codificador, para encadenar.
        """
        self._parts.append(struct.pack("<I", value))
        return self

    def u64(self, value: int) -> Encoder:
        """Agrega un entero sin signo de 64 bits.

        Args:
            value (int): Valor a codificar.

        Returns:
            Encoder: El mismo codificador, para encadenar.
        """
        self._parts.append(struct.pack("<Q", value))
        return self

    def raw(self, data: bytes) -> Encoder:
        """Agrega bytes de longitud fija (``b16``/``b32``).

        Args:
            data (bytes): Bytes a copiar tal cual.

        Returns:
            Encoder: El mismo codificador, para encadenar.
        """
        self._parts.append(bytes(data))
        return self

    def blob(self, data: bytes) -> Encoder:
        """Agrega un campo ``bytes`` (longitud u32 + datos).

        Args:
            data (bytes): Datos a codificar.

        Returns:
            Encoder: El mismo codificador, para encadenar.
        """
        self._parts.append(struct.pack("<I", len(data)) + bytes(data))
        return self

    def text(self, value: str) -> Encoder:
        """Agrega un campo ``str`` (longitud u16 + UTF-8).

        Args:
            value (str): Texto a codificar.

        Returns:
            Encoder: El mismo codificador, para encadenar.
        """
        data = value.encode("utf-8")
        self._parts.append(struct.pack("<H", len(data)) + data)
        return self

    def ext_str(self, tag: int, text: str) -> Encoder:
        """Agrega una extensión de tipo ``str``.

        Args:
            tag (int): Etiqueta de la extensión.
            text (str): Texto a codificar.

        Returns:
            Encoder: El mismo codificador, para encadenar.
        """
        data = text.encode("utf-8")
        self._ext.append((tag, struct.pack("<H", len(data)) + data))
        return self

    def build(self) -> bytes:
        """Une los campos y el bloque de extensiones en orden de etiqueta.

        Returns:
            bytes: Cuerpo codificado.
        """
        ext = b"".join(struct.pack("<HI", tag, len(v)) + v for tag, v in sorted(self._ext))
        return b"".join(self._parts) + struct.pack("<H", len(self._ext)) + ext


class Decoder:
    """Lee un cuerpo AVA1 campo a campo."""

    def __init__(self, data: bytes) -> None:
        """Prepara la lectura.

        Args:
            data (bytes): Cuerpo recibido.
        """
        self._data = memoryview(bytes(data))
        self._pos = 0

    def _take(self, size: int) -> bytes:
        """Consume una cantidad fija de bytes.

        Args:
            size (int): Bytes a leer.

        Returns:
            bytes: Los bytes leídos.

        Raises:
            DecodeError: Si el cuerpo es más corto de lo esperado.
        """
        end = self._pos + size
        if end > len(self._data):
            raise DecodeError("cuerpo AVA1 truncado")
        chunk = bytes(self._data[self._pos:end])
        self._pos = end
        return chunk

    def u8(self) -> int:
        """Lee un entero de 8 bits.

        Returns:
            int: Valor leído.
        """
        return self._take(1)[0]

    def u16(self) -> int:
        """Lee un entero de 16 bits.

        Returns:
            int: Valor leído.
        """
        return struct.unpack("<H", self._take(2))[0]

    def u32(self) -> int:
        """Lee un entero de 32 bits.

        Returns:
            int: Valor leído.
        """
        return struct.unpack("<I", self._take(4))[0]

    def u64(self) -> int:
        """Lee un entero de 64 bits.

        Returns:
            int: Valor leído.
        """
        return struct.unpack("<Q", self._take(8))[0]

    def raw(self, size: int) -> bytes:
        """Lee bytes de longitud fija.

        Args:
            size (int): Longitud (16 o 32).

        Returns:
            bytes: Bytes leídos.
        """
        return self._take(size)

    def blob(self) -> bytes:
        """Lee un campo ``bytes``.

        Returns:
            bytes: Datos leídos.
        """
        return self._take(self.u32())

    def text(self) -> str:
        """Lee un campo ``str``.

        Returns:
            str: Texto leído.

        Raises:
            DecodeError: Si no es UTF-8 válido.
        """
        try:
            return self._take(self.u16()).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DecodeError("texto AVA1 no es UTF-8") from exc

    def extensions(self) -> dict[int, bytes]:
        """Lee el bloque de extensiones y comprueba que no sobren bytes.

        Returns:
            dict[int, bytes]: Etiqueta → valor sin interpretar.

        Raises:
            DecodeError: Si una etiqueta se repite o sobran bytes.
        """
        found: dict[int, bytes] = {}
        for _ in range(self.u16()):
            tag = self.u16()
            value = self._take(self.u32())
            if tag in found:
                raise DecodeError("extensión AVA1 repetida")
            found[tag] = value
        if self._pos != len(self._data):
            raise DecodeError("bytes sobrantes en el cuerpo AVA1")
        return found
