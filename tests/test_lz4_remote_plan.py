from __future__ import annotations

from dataclasses import replace

import pytest

from ffpfsc_converter.domain.lz4 import Lz4Destination
from ffpfsc_converter.services.lz4_plan import (
    find_source,
    mount_prefix,
    output_name,
    suggest_destination,
)
from lz4_fake_client import GAME, IMAGE, INTERNAL, USB

EXT = Lz4Destination("/mnt/ext1/homebrew", "extended", 1, "M.2", 4000, 3900, True)


def test_find_source_ignores_trailing_slash() -> None:
    """Encuentra el juego aunque la ruta elegida termine en barra."""
    assert find_source([GAME, IMAGE], "/data/homebrew/PPSA01234/") == GAME
    assert find_source([GAME, IMAGE], "/data/homebrew/otro") is None


@pytest.mark.parametrize(("path", "expected"), [
    ("/data/homebrew/PPSA01234", "/data"),
    ("/mnt/usb0/homebrew/X.exfat", "/mnt/usb0"),
    ("/mnt/ext1/homebrew", "/mnt/ext1"),
    ("/mnt", "/mnt"),
    ("", "/"),
])
def test_mount_prefix(path: str, expected: str) -> None:
    """Identifica la unidad de una ruta de la PS5."""
    assert mount_prefix(path) == expected


def test_destination_prefers_same_drive() -> None:
    """Sugiere la misma unidad que el original."""
    assert suggest_destination([INTERNAL, USB, EXT], IMAGE.path) == USB
    assert suggest_destination([INTERNAL, USB, EXT], GAME.path) == INTERNAL


def test_destination_falls_back_to_internal() -> None:
    """Si la unidad del original no admite escritura, sugiere la interna."""
    readonly_usb = replace(USB, writable=False)
    assert suggest_destination([EXT, readonly_usb, INTERNAL], IMAGE.path) == INTERNAL


def test_destination_falls_back_to_most_free() -> None:
    """Sin interna escribible, sugiere la unidad escribible con más espacio."""
    readonly_internal = replace(INTERNAL, writable=False)
    assert suggest_destination([USB, EXT, readonly_internal], GAME.path) == EXT
    assert suggest_destination([readonly_internal], GAME.path) is None


def test_output_name_avoids_the_original() -> None:
    """Si ``<destino>/<TITLE_ID>`` es el propio juego, se usa ``<TITLE_ID>-LZ4``."""
    same = replace(GAME, path=f"/data/homebrew/{GAME.title_id}/")
    assert output_name(same, "/data/homebrew") == f"{GAME.title_id}-LZ4"
    nested = replace(GAME, path=f"/data/homebrew/{GAME.title_id}/app")
    assert output_name(nested, "/data/homebrew/") == f"{GAME.title_id}-LZ4"
    assert output_name(replace(GAME, path="/data/homebrew/Astro Bot"), "/data/homebrew") == ""
    assert output_name(same, "/mnt/usb0/homebrew") == ""
