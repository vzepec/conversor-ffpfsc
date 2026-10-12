"""Ajustes de la compresión LZ4 remota: tokens de emparejamiento y ruta del ELF.

exfat2ampr entrega un token por consola al emparejar; se guarda por dirección
de la PS5 para no volver a pedir el código. El ``exfat2ampr.elf`` no viene con
la app: el usuario lo elige una vez y aquí se recuerda su ruta.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ffpfsc_converter.config import E2A_ELF_PATH_KEY, E2A_TOKENS_KEY
from ffpfsc_converter.infrastructure.settings_store import load_settings, save_settings


class Lz4Settings:
    """Lee y guarda los ajustes de exfat2ampr en el archivo de ajustes del usuario."""

    def __init__(self, path: Path | None = None) -> None:
        """Prepara el acceso a los ajustes.

        Args:
            path (Path | None): Archivo de ajustes; ``None`` usa el del usuario.
        """
        self._path = path

    def token(self, host: str) -> str | None:
        """Devuelve el token de emparejamiento guardado para una consola.

        Args:
            host (str): Dirección de la PS5.

        Returns:
            str | None: Token, o ``None`` si esta app no está emparejada con esa consola.
        """
        value = self._tokens().get(host)
        return value if isinstance(value, str) and value else None

    def save_token(self, host: str, token: str) -> None:
        """Guarda el token de emparejamiento de una consola.

        Args:
            host (str): Dirección de la PS5.
            token (str): Token que entregó exfat2ampr.
        """
        tokens = self._tokens()
        tokens[host] = token
        save_settings({E2A_TOKENS_KEY: tokens}, self._path)

    def forget_token(self, host: str) -> None:
        """Olvida el token de una consola (exfat2ampr dejó de aceptarlo).

        Args:
            host (str): Dirección de la PS5.
        """
        tokens = self._tokens()
        if tokens.pop(host, None) is not None:
            save_settings({E2A_TOKENS_KEY: tokens}, self._path)

    def elf_path(self) -> Path | None:
        """Devuelve el ``exfat2ampr.elf`` elegido, si todavía existe.

        Returns:
            Path | None: Ruta del ELF, o ``None`` si no se eligió o ya no está.
        """
        value = load_settings(self._path).get(E2A_ELF_PATH_KEY)
        if not isinstance(value, str) or not value:
            return None
        path = Path(value)
        return path if path.is_file() else None

    def save_elf_path(self, path: Path) -> None:
        """Recuerda el ``exfat2ampr.elf`` que eligió el usuario.

        Args:
            path (Path): Archivo ELF local.
        """
        save_settings({E2A_ELF_PATH_KEY: str(path)}, self._path)

    def _tokens(self) -> dict[str, Any]:
        """Lee el diccionario de tokens por consola.

        Returns:
            dict[str, Any]: Copia de los tokens guardados (vacía si no hay o está dañado).
        """
        value = load_settings(self._path).get(E2A_TOKENS_KEY)
        return dict(value) if isinstance(value, dict) else {}
