from __future__ import annotations

import json
from pathlib import Path

from ffpfsc_converter.config import E2A_ELF_PATH_KEY
from ffpfsc_converter.services.lz4_settings import Lz4Settings


def test_tokens_are_kept_per_console(tmp_path: Path) -> None:
    """Guarda un token por consola y lo devuelve solo para esa dirección."""
    settings = Lz4Settings(tmp_path / "settings.json")
    settings.save_token("10.0.0.2", "uno")
    settings.save_token("10.0.0.3", "dos")
    assert settings.token("10.0.0.2") == "uno"
    assert settings.token("10.0.0.3") == "dos"
    assert settings.token("10.0.0.4") is None


def test_forget_token_only_removes_that_console(tmp_path: Path) -> None:
    """Olvidar un token conserva los de otras consolas."""
    settings = Lz4Settings(tmp_path / "settings.json")
    settings.save_token("10.0.0.2", "uno")
    settings.save_token("10.0.0.3", "dos")
    settings.forget_token("10.0.0.2")
    settings.forget_token("10.0.0.9")
    assert settings.token("10.0.0.2") is None
    assert settings.token("10.0.0.3") == "dos"


def test_tokens_keep_other_settings(tmp_path: Path) -> None:
    """Guardar un token no borra los demás ajustes del usuario."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"preset": "Equilibrado"}), encoding="utf-8")
    Lz4Settings(path).save_token("ps5", "t")
    assert json.loads(path.read_text(encoding="utf-8"))["preset"] == "Equilibrado"


def test_damaged_tokens_are_ignored(tmp_path: Path) -> None:
    """Un valor de tokens dañado se trata como si no hubiera ninguno."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"e2a_tokens": ["x"]}), encoding="utf-8")
    assert Lz4Settings(path).token("ps5") is None


def test_elf_path_is_remembered_while_it_exists(tmp_path: Path) -> None:
    """Devuelve el ELF elegido y ``None`` si se borró o nunca se eligió."""
    settings = Lz4Settings(tmp_path / "settings.json")
    assert settings.elf_path() is None
    elf = tmp_path / "exfat2ampr.elf"
    elf.write_bytes(b"\x7fELF")
    settings.save_elf_path(elf)
    assert settings.elf_path() == elf
    elf.unlink()
    assert settings.elf_path() is None


def test_elf_path_ignores_invalid_value(tmp_path: Path) -> None:
    """Un valor que no es texto no se toma como ruta."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({E2A_ELF_PATH_KEY: 3}), encoding="utf-8")
    assert Lz4Settings(path).elf_path() is None
