from __future__ import annotations

import os
import random
from pathlib import Path

import pytest

from ffpfsc_converter.domain.models import ConversionJob, FileEntry
from ffpfsc_converter.services.lz4_estimator import estimate_lz4, packed_end, stored_size
from ffpfsc_converter.services.lz4_local_files import (
    copy_loose,
    discard,
    lz4_output_path,
    workspace_for,
)
from ffpfsc_converter.services.lz4_local_publish import _publish


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
    estimate = estimate_lz4(files, root, [1, 9], sample_blocks=16)
    assert all(50_000 <= total < 100_000 for total in estimate.totals.values())
    assert estimate.loose == 50_000


def test_fast_lz4_is_estimated_bigger_than_hc(tmp_path: Path) -> None:
    """El modo rápido comprime menos que HC, así que su peso estimado es mayor."""
    root = tmp_path / "game"
    (root / "assets").mkdir(parents=True)
    words = [os.urandom(3).hex() for _ in range(400)]
    rng = random.Random(1)
    data = " ".join(rng.choice(words) for _ in range(400_000)).encode()[:2_000_000]
    (root / "assets/texto.tex").write_bytes(data)
    files = [FileEntry(str(root / "assets/texto.tex"), len(data))]
    totals = estimate_lz4(files, root, [1, 9, 12], sample_blocks=32).totals
    assert totals[1] > totals[9] >= totals[12]


def test_blocks_that_save_little_are_stored_raw() -> None:
    """Un bloque de 64 KiB va crudo si ahorra menos de 8 KiB o del 12,5 %."""
    page = 64 * 1024
    assert stored_size(page, page - 4 * 1024) == page
    assert stored_size(page, page // 2) == page // 2
    assert stored_size(page, page + 100) == page


def test_chunks_never_straddle_a_page() -> None:
    """Dos bloques de 40 KiB no caben en una página: el segundo empieza en la siguiente."""
    kib = 1024
    assert packed_end([40 * kib, 40 * kib]) == 64 * kib + 40 * kib
    assert packed_end([20 * kib, 20 * kib, 20 * kib]) == 60 * kib
    assert packed_end([100, 100]) == 128 + 100  # alineados a 64 bytes
    assert packed_end([64 * kib, 64 * kib]) == 128 * kib
