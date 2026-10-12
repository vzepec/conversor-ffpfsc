from __future__ import annotations

import os
from pathlib import Path

import pytest

from ffpfsc_converter.domain.models import ConversionJob, FileEntry
from ffpfsc_converter.services.lz4_estimator import estimate_lz4
from ffpfsc_converter.services.lz4_local_files import (
    _publish,
    copy_loose,
    discard,
    lz4_output_path,
    workspace_for,
)


def _job(tmp_path: Path) -> ConversionJob:
    """Crea un trabajo cuya salida va junto al juego."""
    game = tmp_path / "PPSA01234"
    game.mkdir()
    return ConversionJob(game, game, tmp_path / "PPSA01234.ffpfsc")


def test_paths_are_next_to_the_output_and_never_inside_the_game(tmp_path: Path) -> None:
    """La carpeta LZ4, la temporal y la parcial quedan junto a la salida, fuera del juego."""
    ws = workspace_for(_job(tmp_path))
    assert ws.output == lz4_output_path(_job_like(tmp_path)) == tmp_path / "PPSA01234-LZ4"
    assert ws.work.parent == ws.partial.parent == tmp_path
    assert ws.root not in ws.work.parents and ws.work.name.startswith(".")


def _job_like(tmp_path: Path) -> ConversionJob:
    """Devuelve un trabajo equivalente sin crear carpetas."""
    game = tmp_path / "PPSA01234"
    return ConversionJob(game, game, tmp_path / "PPSA01234.ffpfsc")


def test_publish_replaces_and_restores_on_failure(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """Publicar reemplaza la salida anterior; si el renombrado falla, la restaura."""
    output, partial = tmp_path / "out", tmp_path / "out.parcial"
    output.mkdir(), partial.mkdir()
    (output / "viejo").write_text("v")
    (partial / "nuevo").write_text("n")
    _publish(partial, output)
    assert [p.name for p in output.iterdir()] == ["nuevo"] and not partial.exists()
    partial.mkdir()
    real_rename = Path.rename

    def failing(self: Path, target: Path) -> Path:
        """Falla solo al publicar la carpeta parcial."""
        if self == partial:
            raise OSError("disco lleno")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", failing)
    with pytest.raises(OSError):
        _publish(partial, output)
    assert [p.name for p in output.iterdir()] == ["nuevo"]


def test_copy_loose_refuses_paths_outside_the_game(tmp_path: Path) -> None:
    """Una ruta suelta que sale del juego se rechaza; las válidas se copian."""
    job = _job(tmp_path)
    (job.game_root / "eboot.bin").write_bytes(b"x")
    ws = workspace_for(job)
    ws.partial.mkdir()
    assert copy_loose(ws, ["eboot.bin"], lambda _n: True)
    assert (ws.partial / "eboot.bin").read_bytes() == b"x"
    with pytest.raises(OSError):
        copy_loose(ws, ["../fuera.txt"], lambda _n: True)


def test_discard_keeps_a_previous_output(tmp_path: Path) -> None:
    """Descartar borra lo temporal y lo parcial, nunca la salida final."""
    ws = workspace_for(_job(tmp_path))
    for folder in (ws.work, ws.partial, ws.output):
        folder.mkdir()
    discard(ws)
    assert ws.output.exists() and not ws.work.exists() and not ws.partial.exists()


def test_lz4_estimate_counts_loose_files_whole(tmp_path: Path) -> None:
    """Lo suelto cuenta completo y lo comprimible se reduce según la muestra."""
    root = tmp_path / "game"
    (root / "assets").mkdir(parents=True)
    files = []
    for rel, data in (("eboot.bin", os.urandom(50_000)),
                      ("assets/a.tex", b"\0" * 1_000_000)):
        (root / rel).write_bytes(data)
        files.append(FileEntry(str(root / rel), len(data)))
    estimate = estimate_lz4(files, root, sample_blocks=16)
    assert 50_000 <= estimate < 100_000
