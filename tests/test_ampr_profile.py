from __future__ import annotations

import fnmatch

import pytest

from ffpfsc_converter.services.ampr_profile import (
    AmprAction,
    build_profile,
    classify,
    escape_glob,
)


@pytest.mark.parametrize(("path", "action"), [
    ("eboot.bin", AmprAction.LOOSE),
    ("contentids.json", AmprAction.LOOSE),                    # raíz: siempre suelto
    ("sce_sys/param.json", AmprAction.LOOSE),
    ("SCE_MODULE/libc.prx", AmprAction.LOOSE),                # sin distinguir mayúsculas
    ("live/content/paks/pakchunk0-ps5.pak", AmprAction.LOOSE),
    ("live/content/paks/pakchunk0-ps5.utoc", AmprAction.LOOSE),
    ("live/content/paks/pakchunk0-ps5.ucas", AmprAction.COMPRESS),
    ("live/content/movies/intro.MP4", AmprAction.LOOSE),
    ("data/soundbank_es.bnk", AmprAction.LOOSE),              # prefijo suelto
    ("Audio/sfx/explosion.bnk", AmprAction.AUDIO),
    ("assets/textures/rock.tex", AmprAction.COMPRESS),
    ("fakelib/libSceAmpr.sprx", AmprAction.LOOSE),
])
def test_classify_follows_generic_rules(path: str, action: AmprAction) -> None:
    """Clasifica sin distinguir mayúsculas con las reglas genéricas de exfat2ampr."""
    assert classify(path) is action


def test_escaped_paths_only_match_themselves() -> None:
    """Una ruta con ``[``, ``*`` o ``?`` se escapa para que ``fnmatch`` la tome literal."""
    path = "data/[v2]/a*b?.tex"
    pattern = escape_glob(path)
    assert fnmatch.fnmatchcase(path, pattern)
    assert not fnmatch.fnmatchcase("data/v/axxb1.tex", pattern)


def test_profile_lists_and_mode() -> None:
    """Separa comprimidos y audio, deja fuera lo suelto y elige rápido o HC según el nivel."""
    files = ["eboot.bin", "assets/a.tex", "audio/b.bnk", "movies/c.mp4"]
    fast, hc = build_profile(files, 1, 4), build_profile(files, 12, 0)
    assert fast.compress == ("assets/a.tex",) and fast.audio == ("audio/b.bnk",)
    assert 'compression_mode = "fast"' in fast.toml
    assert 'compression_mode = "hc"' in hc.toml and "compression_level = 12" in hc.toml
    assert "workers = 1" in hc.toml and 'default_action = "loose"' in hc.toml


def test_empty_lists_do_not_produce_rules() -> None:
    """Sin archivos de audio no hay regla de audio: en ampr_pack una lista vacía vale «**»."""
    profile = build_profile(["eboot.bin", "assets/a.tex"], 9, 4)
    assert profile.audio == () and "audio.txt" not in profile.toml
    assert "compress.txt" in profile.toml
    nothing = build_profile(["eboot.bin", "movies/a.mp4"], 9, 4)
    assert "[[rule]]" not in nothing.toml
