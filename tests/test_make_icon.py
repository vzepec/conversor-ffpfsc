from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import make_icon


def test_make_icons_writes_png_and_multi_size_ico(tmp_path: Path) -> None:
    """Genera el PNG para Linux y el ICO con varios tamaños para Windows."""
    png, ico = make_icon.make_icons(tmp_path / "assets")
    assert Image.open(png).size == (make_icon.PNG_SIZE, make_icon.PNG_SIZE)
    with Image.open(ico) as image:
        assert (16, 16) in image.info["sizes"] and (256, 256) in image.info["sizes"]
