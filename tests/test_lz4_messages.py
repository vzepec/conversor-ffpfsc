from __future__ import annotations

import pytest

from ffpfsc_converter.services import lz4_messages as msg
from ffpfsc_converter.services.lz4_messages import PAIR_BLOCKED_TEXT, engine_error_text

_JARGON = ("libSceAmpr", "AMPR", "fakelib", "ShadowMountPlus", "token", "API", "6972", "9021")


@pytest.mark.parametrize(("code", "fragment"), [
    ("queue_full", "en espera"),
    ("dest_unavailable", "unidad de destino"),
    ("bad_path", "ubicación"),
    ("bad_name", "nombre de carpeta"),
    ("nothing_to_retry", "reintentar"),
    ("busy", "ocupada"),
    ("cannot resume", "reanudar"),
    ("Cannot_Resume", "reanudar"),
])
def test_known_codes_are_translated(code: str, fragment: str) -> None:
    """Cada código conocido de exfat2ampr tiene su mensaje en español."""
    assert fragment in engine_error_text(code)


def test_blocked_uses_pairing_text() -> None:
    """El bloqueo por intentos explica que hay que esperar y que el código cambió."""
    assert engine_error_text("blocked") == PAIR_BLOCKED_TEXT
    assert "Espera un minuto" in PAIR_BLOCKED_TEXT and "código nuevo" in PAIR_BLOCKED_TEXT


def test_unknown_code_is_generic() -> None:
    """Un código desconocido da un mensaje genérico que remite a Registros, sin el código."""
    text = engine_error_text("weird_code")
    assert "Registros" in text and "weird_code" not in text
    assert engine_error_text("") == text


def test_messages_are_short_and_plain() -> None:
    """Los mensajes no usan jerga técnica y son de una o dos frases."""
    texts = [value for name, value in vars(msg).items()
             if name.endswith("_TEXT") and isinstance(value, str)]
    texts += [engine_error_text(code) for code in ("queue_full", "busy", "bad_response")]
    for text in texts:
        assert not any(word in text for word in _JARGON), text
        assert len(text) <= 120, text
    assert "etaHEN" in msg.ELF_SEND_ERROR_TEXT
