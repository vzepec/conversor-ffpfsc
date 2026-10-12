from __future__ import annotations

from pathlib import Path

import pytest

from ffpfsc_converter.infrastructure.ampr_tools import (
    AmprTools,
    PackPaths,
    parse_pack_progress,
    parse_pack_summary,
)

SUMMARY = ["[pack 100%] complete: files 2/2, elapsed 00:00:01", "{",
           '  "files_packed": 2,', '  "logical_bytes": 100,', '  "stored_bytes": 40,',
           '  "loose_paths": [', '    "eboot.bin"', "  ]", "}"]


def test_commands_use_the_app_python_and_never_write_into_the_game(tmp_path: Path) -> None:
    """Los comandos usan el intérprete dado, sin búfer, y el índice va fuera del juego."""
    tools = AmprTools(tmp_path / "tools", python="py")
    root, work = tmp_path / "game", tmp_path / "work"
    index = tools.index_command(root, work / "ampr_emu.index")
    assert index[:2] == ["py", "-u"] and index[-2:] == ["--output", str(work / "ampr_emu.index")]
    pack = tools.pack_command(PackPaths(root, work / "i", work / "p.toml", work / "out"), 0)
    assert pack[3] == "pack" and pack[pack.index("--workers") + 1] == "1"
    assert tools.verify_command(work / "out/ampr_assets.index", root)[3:6] == [
        "verify", "--index", str(work / "out/ampr_assets.index")]


def test_progress_lines() -> None:
    """Reconoce el avance de ``ampr_pack.py`` y descarta el resto."""
    update = parse_pack_progress("[pack  10%] packing: files 0/13, 0 B/12.5 MiB, elapsed 0")
    assert update is not None and (update.percent, update.phase) == (10, "packing")
    assert parse_pack_progress("indexed 18 files") is None


def test_summary_is_read_from_the_last_json() -> None:
    """Lee los archivos sueltos y tamaños del resumen final."""
    summary = parse_pack_summary(SUMMARY)
    assert summary.loose_paths == ("eboot.bin",) and summary.stored_bytes == 40
    with pytest.raises(ValueError):
        parse_pack_summary(["sin resumen"])
