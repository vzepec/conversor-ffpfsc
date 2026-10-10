from __future__ import annotations

import json
from pathlib import Path

import pytest

from ffpfsc_converter.domain.models import GameInfo
from ffpfsc_converter.infrastructure import mkpfs_adapter
from ffpfsc_converter.services.metadata import parse_param_json, read_game_info


def _param(**data: object) -> bytes:
    return json.dumps(data).encode()


def test_prefers_default_language() -> None:
    info = parse_param_json(_param(
        titleId="PPSA1", masterVersion="01.00",
        localizedParameters={
            "defaultLanguage": "ja-JP",
            "ja-JP": {"titleName": "ゲーム"},
            "en-US": {"titleName": "Game"},
        },
    ))
    assert info == GameInfo("ゲーム", "PPSA1", "01.00")


def test_falls_back_to_spanish_then_any_language() -> None:
    info = parse_param_json(_param(localizedParameters={"es-ES": {"titleName": " Juego "}}))
    assert info.title == "Juego"
    info = parse_param_json(_param(localizedParameters={"fr-FR": {"titleName": "Jeu"}}))
    assert info.title == "Jeu"


def test_top_level_title_and_bom() -> None:
    data = b"\xef\xbb\xbf" + _param(titleName="Plain")
    assert parse_param_json(data).title == "Plain"


def test_non_object_json() -> None:
    assert parse_param_json(b"[]") == GameInfo()


def test_read_game_info_from_folder(game_folder: Path) -> None:
    info = read_game_info(game_folder / "PPSA00000-app")
    assert info == GameInfo("Test Game", "PPSA00000", "01.000.000")


def test_read_game_info_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_target: Path) -> GameInfo:
        raise RuntimeError("imagen corrupta")

    monkeypatch.setattr(mkpfs_adapter, "read_metadata", boom)
    bogus = tmp_path / "x.ffpkg"
    bogus.write_bytes(b"garbage")
    assert read_game_info(bogus) == GameInfo()
