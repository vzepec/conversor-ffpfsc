from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def game_folder(tmp_path: Path) -> Path:
    """Carpeta de juego mínima: ``Juego/PPSA00000-app/{eboot.bin, sce_sys/param.json}``."""
    root = tmp_path / "Juego" / "PPSA00000-app"
    (root / "sce_sys").mkdir(parents=True)
    (root / "eboot.bin").write_bytes(b"\x00" * 1024)
    (root / "sce_sys" / "param.json").write_text(json.dumps({
        "titleId": "PPSA00000",
        "contentVersion": "01.000.000",
        "localizedParameters": {
            "defaultLanguage": "en-US",
            "en-US": {"titleName": "Test Game"},
        },
    }))
    return tmp_path / "Juego"
