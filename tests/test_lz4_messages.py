from __future__ import annotations

import pytest

from ffpfsc_converter.config import ELF_LOADER_PORT
from ffpfsc_converter.services.lz4_messages import (
    PAIR_BLOCKED_TEXT,
    elf_send_error_text,
    engine_error_text,
    launch_timeout_text,
    network_error_text,
    source_missing_text,
)


@pytest.mark.parametrize(("code", "fragment"), [
    ("queue_full", "cola llena"),
    ("dest_unavailable", "unidad de destino"),
    ("bad_path", "ruta del juego"),
    ("bad_name", "nombre de la carpeta"),
    ("nothing_to_retry", "reintentar"),
    ("busy", "ocupado"),
    ("cannot resume", "reanudar"),
    ("Cannot_Resume", "reanudar"),
])
def test_known_codes_are_translated(code: str, fragment: str) -> None:
    """Cada código conocido de exfat2ampr tiene su mensaje en español."""
    assert fragment in engine_error_text(code, "english detail")


def test_blocked_uses_pairing_text() -> None:
    """El bloqueo por intentos explica que hay que esperar y que el código cambió."""
    assert engine_error_text("blocked", "") == PAIR_BLOCKED_TEXT
    assert "espera un minuto" in PAIR_BLOCKED_TEXT


def test_unknown_code_shows_fallback() -> None:
    """Un código desconocido muestra el detalle que dio exfat2ampr."""
    assert engine_error_text("weird", "something broke") == (
        "exfat2ampr rechazó la orden (something broke).")
    assert "weird" in engine_error_text("weird", "")
    assert "motivo desconocido" in engine_error_text("", "")


def test_connection_texts_name_host_and_ports() -> None:
    """Los mensajes de conexión indican la consola y el puerto implicado."""
    assert "10.0.0.2" in network_error_text("10.0.0.2")
    assert str(ELF_LOADER_PORT) in elf_send_error_text("10.0.0.2")
    assert str(ELF_LOADER_PORT) in launch_timeout_text("10.0.0.2")
    assert "/data/x" in source_missing_text("/data/x")
