from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions, ProgressUpdate
from ffpfsc_converter.infrastructure.mkpfs_adapter import (
    build_pack_command,
    parse_progress,
    split_lines,
)


def test_parse_progress() -> None:
    assert parse_progress("[2/4] 37% compress @ 512.3 MB/s") == ProgressUpdate(
        37, "compress", "512.3 MB/s")
    assert parse_progress("[1/4] 5% scan") == ProgressUpdate(5, "scan", None)
    assert parse_progress("Writing 50% done") is None
    assert parse_progress("[x] nada") is None


def test_split_lines_handles_carriage_returns_across_chunks() -> None:
    chunks = [b"[1] 1% sc", b"an\r[1] 2% scan\r", b"\nhola\n", b"fin"]
    assert list(split_lines(chunks)) == ["[1] 1% scan", "[1] 2% scan", "hola", "fin"]


def test_build_command_for_folder(game_folder: Path) -> None:
    root = game_folder / "PPSA00000-app"
    job = ConversionJob(game_folder, root, Path("/out/x.ffpfsc"))
    cmd = build_pack_command(job, ConversionOptions(6, 4, False), python_executable="py")
    assert cmd[:6] == ["py", "-u", "-m", "mkpfs", "pack", "folder"]
    assert cmd[cmd.index("--compression-level") + 1] == "6"
    assert cmd[cmd.index("--cpu-count") + 1] == "4"
    assert cmd[cmd.index("--compression-backend") + 1] == "zlib-ng"
    assert cmd[cmd.index("--temp-folder") + 1] == "/out"
    assert "--require-game-files" in cmd
    assert "--verify-structure" in cmd
    assert cmd[-2:] == [str(root), "/out/x.ffpfsc"]


def test_build_command_for_image_with_full_verify(tmp_path: Path) -> None:
    image = tmp_path / "g.exfat"
    image.touch()
    job = ConversionJob(image, image, tmp_path / "g.ffpfsc")
    cmd = build_pack_command(job, ConversionOptions(3, 1, True))
    assert cmd[5] == "file"
    assert "--require-game-files" not in cmd
    assert "--verify" in cmd
