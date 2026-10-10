from __future__ import annotations

from pathlib import Path

import pytest

from ffpfsc_converter.errors import GameNotFoundError, SourceNotFoundError, UnsupportedFormatError
from ffpfsc_converter.services.discovery import (
    create_job,
    find_game_root,
    find_image_file,
    output_path_for,
    resolve_game_root,
)


def test_find_game_root_descends_into_subfolders(game_folder: Path) -> None:
    """Encuentra eboot.bin dentro de subcarpetas."""
    assert find_game_root(game_folder) == game_folder / "PPSA00000-app"


def test_find_game_root_respects_depth(tmp_path: Path) -> None:
    """Ignora carpetas más profundas que el límite."""
    deep = tmp_path / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "eboot.bin").touch()
    assert find_game_root(tmp_path, max_depth=3) is None
    assert find_game_root(tmp_path, max_depth=4) == deep


def test_find_image_file_returns_largest(tmp_path: Path) -> None:
    """Elige la imagen más grande sin distinguir mayúsculas en la extensión."""
    (tmp_path / "small.exfat").write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "big.FFPKG").write_bytes(b"x" * 10)
    assert find_image_file(tmp_path) == tmp_path / "sub" / "big.FFPKG"


def test_resolve_errors(tmp_path: Path) -> None:
    """Lanza el error de dominio adecuado para cada origen inválido."""
    with pytest.raises(SourceNotFoundError):
        resolve_game_root(tmp_path / "nope")
    (tmp_path / "a.zip").touch()
    with pytest.raises(UnsupportedFormatError):
        resolve_game_root(tmp_path / "a.zip")
    (tmp_path / "empty").mkdir()
    with pytest.raises(GameNotFoundError):
        resolve_game_root(tmp_path / "empty")


def test_output_path_next_to_source_or_custom_dir(tmp_path: Path) -> None:
    """Ubica la salida junto al origen o en la carpeta elegida."""
    image = tmp_path / "game.exfat"
    image.touch()
    assert output_path_for(image, None) == tmp_path / "game.ffpfsc"
    assert output_path_for(tmp_path, Path("/out")) == Path("/out") / f"{tmp_path.name}.ffpfsc"


def test_create_job(game_folder: Path) -> None:
    """Crea un trabajo pendiente con la raíz del juego detectada."""
    job = create_job(game_folder)
    assert job.game_root == game_folder / "PPSA00000-app"
    assert job.output == game_folder.parent / "Juego.ffpfsc"
    assert job.is_queued
