"""Identidad de la app y consolas emparejadas (AVA1).

La identidad es una clave X25519 propia que se crea una vez. Tras emparejar,
se guarda la clave pública de cada PS5 por dirección: la siguiente conexión no
pide código y se rechaza un equipo que se haga pasar por la consola.
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

_IDENTITY_FILE = "ava1_identity.key"
_PEERS_FILE = "ava1_peers.json"


class TrustStore:
    """Archivos de identidad y consolas conocidas en la carpeta de ajustes."""

    def __init__(self, directory: Path) -> None:
        """Prepara el almacén.

        Args:
            directory (Path): Carpeta de ajustes de la aplicación.
        """
        self._dir = directory

    def identity(self) -> X25519PrivateKey:
        """Obtiene la identidad de la app, creándola la primera vez.

        Returns:
            X25519PrivateKey: Clave privada estática.

        Raises:
            OSError: Si no se puede crear la carpeta o guardar la clave.
        """
        path = self._dir / _IDENTITY_FILE
        with contextlib.suppress(OSError, ValueError):
            return X25519PrivateKey.from_private_bytes(bytes.fromhex(path.read_text().strip()))
        key = X25519PrivateKey.from_private_bytes(os.urandom(32))
        self._dir.mkdir(parents=True, exist_ok=True)
        raw = key.private_bytes_raw().hex()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(raw)
        return key

    def known_key(self, host: str) -> bytes | None:
        """Busca la clave pública de una consola ya emparejada.

        Args:
            host (str): Dirección de la consola.

        Returns:
            bytes | None: Clave de 32 bytes, o ``None`` si nunca se emparejó.
        """
        entry = self._peers().get(host)
        try:
            return bytes.fromhex(entry["key"]) if entry else None
        except (KeyError, TypeError, ValueError):
            return None

    def remember(self, host: str, key: bytes, name: str) -> None:
        """Guarda la clave pública de una consola emparejada.

        Args:
            host (str): Dirección de la consola.
            key (bytes): Clave pública estática de la consola.
            name (str): Nombre que informó la consola.

        Raises:
            OSError: Si no se puede escribir el archivo.
        """
        peers = self._peers()
        peers[host] = {"key": key.hex(), "name": name}
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self._dir / (_PEERS_FILE + ".tmp")
        tmp.write_text(json.dumps(peers, indent=2), encoding="utf-8")
        os.replace(tmp, self._dir / _PEERS_FILE)

    def _peers(self) -> dict[str, dict[str, str]]:
        """Lee las consolas conocidas.

        Returns:
            dict[str, dict[str, str]]: Dirección → ``{"key", "name"}``; vacío si no hay archivo.
        """
        try:
            data = json.loads((self._dir / _PEERS_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
