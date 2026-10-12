from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from ffpfsc_converter.domain.events import JobFinished, JobProgress
from ffpfsc_converter.domain.models import ConversionOptions, JobState, OutputFormat
from ffpfsc_converter.infrastructure.ampr_tools import AmprTools
from ffpfsc_converter.services.conversion import ConversionRunner
from ffpfsc_converter.services.discovery import create_job
from ffpfsc_converter.services.lz4_local import (
    FOLDERS_ONLY_TEXT,
    MISSING_COMPONENTS_TEXT,
    Lz4LocalConversion,
)
from ffpfsc_converter.services.lz4_local_files import lz4_output_path, workspace_for
from ffpfsc_converter.services.lz4_local_steps import (
    Lz4Components,
    StepContext,
    installed_components,
)

LZ4 = ConversionOptions(9, 2, True, output_format=OutputFormat.LZ4)


def _game(root: Path) -> Path:
    """Crea un juego sintético compatible: comprimible, incompresible, audio y sueltos."""
    (root / "sce_sys").mkdir(parents=True)
    (root / "sce_sys/param.json").write_text(json.dumps({"titleId": "PPSA01234"}))
    (root / "eboot.bin").write_bytes(b"\x7fELF libkernel libSceAmpr " + os.urandom(2048))
    (root / "assets").mkdir()
    (root / "assets/texturas.tex").write_bytes((b"textura repetida " * 40000)[:600_000])
    (root / "assets/ruido.tex").write_bytes(os.urandom(300_000))
    (root / "audio").mkdir()
    (root / "audio/sfx.bnk").write_bytes((b"pcm " * 50000)[:200_000])
    (root / "movies").mkdir()
    (root / "movies/intro.mp4").write_bytes(os.urandom(100_000))
    return root


def _tree_hash(root: Path) -> str:
    """Resume el contenido de una carpeta para comprobar que no cambió."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode() + path.read_bytes())
    return digest.hexdigest()


def _run(job, options: ConversionOptions, factory=None) -> JobFinished:
    """Convierte un trabajo con el runner real y devuelve su ``JobFinished``."""
    events: list[object] = []
    runner = ConversionRunner(events.append, factory) if factory else ConversionRunner(
        events.append)
    runner.start([job], options).join(timeout=300)
    return next(e for e in events if isinstance(e, JobFinished))


@pytest.mark.skipif(installed_components() is None, reason="sin componentes de ampr_emu")
def test_real_tools_build_a_verified_lz4_folder(tmp_path: Path) -> None:
    """Con ampr_emu real: carpeta final completa, original intacto y sin temporales."""
    game = _game(tmp_path / "PPSA01234")
    before = _tree_hash(game)
    job = create_job(game)
    finished = _run(job, LZ4)
    assert finished.result.succeeded and job.state is JobState.SUCCEEDED
    out = job.output
    assert out == lz4_output_path(create_job(game)) and out.is_dir()
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert {"eboot.bin", "sce_sys/param.json", "movies/intro.mp4", "ampr_emu.index",
            "ampr_assets.index", "fakelib/libSceAmpr.sprx"} <= names
    assert "assets/texturas.tex" not in names and any(n.endswith(".pak") for n in names)
    assert _tree_hash(game) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["PPSA01234", "PPSA01234-LZ4"]
    tools = installed_components().tools
    check = subprocess.run([sys.executable, str(tools.tools_dir / "ampr_pack.py"), "verify",
                            "--index", str(out / "ampr_assets.index")], capture_output=True)
    assert check.returncode == 0


@pytest.mark.skipif(installed_components() is None, reason="sin componentes de ampr_emu")
def test_verification_can_be_skipped(tmp_path: Path) -> None:
    """Sin verificación completa, LZ4 no ejecuta el paso de comprobación pero termina bien."""
    from ffpfsc_converter.config import LZ4_VERIFY_PHASE

    job = create_job(_game(tmp_path / "PPSA01234"))
    events: list[object] = []
    options = ConversionOptions(9, 2, False, output_format=OutputFormat.LZ4)
    ConversionRunner(events.append).start([job], options).join(timeout=300)
    phases = {e.progress.phase for e in events if isinstance(e, JobProgress)}
    assert {"scan", "compress"} <= phases and LZ4_VERIFY_PHASE not in phases
    assert next(e for e in events if isinstance(e, JobFinished)).result.succeeded


class _FakeProcess:
    """Proceso falso: entrega líneas y termina con el código indicado."""

    def __init__(self, lines: list[str], code: int) -> None:
        """Guarda la salida y el código."""
        self._lines, self._code, self.terminated = lines, code, False

    def lines(self) -> Iterator[str]:
        """Entrega las líneas fijas."""
        yield from self._lines

    def wait(self) -> int:
        """Devuelve el código fijo."""
        return self._code

    def terminate(self) -> None:
        """Registra que se pidió terminar."""
        self.terminated = True


@pytest.mark.skipif(installed_components() is None, reason="sin componentes de ampr_emu")
def test_failed_step_leaves_no_partial_folders(tmp_path: Path) -> None:
    """Si una herramienta falla, el trabajo falla y no quedan temporales ni salida."""
    job = create_job(_game(tmp_path / "PPSA01234"))
    finished = _run(job, LZ4, lambda _cmd: _FakeProcess(["error: algo salió mal"], 2))
    assert not finished.result.succeeded and "algo salió mal" in finished.result.message
    ws = workspace_for(job)
    assert not ws.work.exists() and not ws.partial.exists() and not ws.output.exists()


def test_missing_components_and_images_fail_with_a_clear_message(tmp_path: Path) -> None:
    """Sin componentes instalados, o con una imagen, falla con un mensaje claro."""
    ctx = StepContext(lambda _e: None, lambda _cmd: _FakeProcess([], 0), threading.Event(),
                      lambda _p: None)
    job = create_job(_game(tmp_path / "PPSA01234"))
    assert Lz4LocalConversion(ctx, lambda: None).run(job, LZ4).message == MISSING_COMPONENTS_TEXT
    image = tmp_path / "juego.exfat"
    image.write_bytes(b"x")
    components = Lz4Components(AmprTools(tmp_path), tmp_path / "libSceAmpr.sprx")
    result = Lz4LocalConversion(ctx, lambda: components).run(create_job(image), LZ4)
    assert result.message == FOLDERS_ONLY_TEXT and not result.succeeded


@pytest.mark.skipif(installed_components() is None, reason="sin componentes de ampr_emu")
def test_real_tools_without_audio_keep_unlisted_files_loose(tmp_path: Path) -> None:
    """Sin carpeta de audio, lo que no está en las listas (``.pak``) queda suelto."""
    game = _game(tmp_path / "PPSA01234")
    for path in (game / "audio").iterdir():
        path.unlink()
    (game / "audio").rmdir()
    (game / "assets/archivo.pak").write_bytes(os.urandom(200_000))
    job = create_job(game)
    assert _run(job, LZ4).result.succeeded
    assert (job.output / "assets/archivo.pak").is_file()
    assert (job.output / "assets/ruido.tex").exists() is False


@pytest.mark.skipif(installed_components() is None, reason="sin componentes de ampr_emu")
def test_packing_more_files_than_planned_is_stopped(tmp_path: Path) -> None:
    """Si ``ampr_pack`` anuncia más archivos de los previstos, se detiene y no queda nada."""
    job = create_job(_game(tmp_path / "PPSA01234"))
    processes: list[_FakeProcess] = []

    def factory(command: list[str]) -> _FakeProcess:
        """Simula el índice bien y un empaquetado que anuncia 999 archivos."""
        lines = ["[pack  10%] packing: files 0/999, 0 B/1 GiB"] if "pack" in command else []
        processes.append(_FakeProcess(lines, 0))
        return processes[-1]

    finished = _run(job, LZ4, factory)
    assert not finished.result.succeeded and "999" in finished.result.message
    assert processes[-1].terminated and not workspace_for(job).work.exists()


@pytest.mark.skipif(installed_components() is None, reason="sin componentes de ampr_emu")
def test_packing_stops_when_the_disk_runs_low(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """Si el disco de destino se queda sin espacio, se detiene y no queda nada."""
    import ffpfsc_converter.services.lz4_local as lz4_local
    monkeypatch.setattr(lz4_local, "free_space", lambda _path: 0)
    job = create_job(_game(tmp_path / "PPSA01234"))
    lines = ["[pack  10%] packing: files 0/1, 0 B/1 GiB"]
    finished = _run(job, LZ4, lambda cmd: _FakeProcess(lines if "pack" in cmd else [], 0))
    assert finished.result.message == lz4_local.DISK_FULL_TEXT
    assert not workspace_for(job).work.exists()


@pytest.mark.skipif(installed_components() is None, reason="sin componentes de ampr_emu")
def test_linked_loose_files_never_change_the_original(tmp_path: Path) -> None:
    """Lo suelto se enlaza, y escribir el índice y la biblioteca propios no toca el original."""
    game = _game(tmp_path / "PPSA01234")
    (game / "ampr_emu.index").write_bytes(b"indice viejo del juego")
    (game / "fakelib").mkdir()
    (game / "fakelib/libSceAmpr.sprx").write_bytes(b"emulador sin paquetes")
    before = _tree_hash(game)
    job = create_job(game)
    assert _run(job, LZ4).result.succeeded
    assert _tree_hash(game) == before
    out = job.output
    assert (out / "ampr_emu.index").read_bytes() != b"indice viejo del juego"
    runtime = installed_components().runtime
    assert (out / "fakelib/libSceAmpr.sprx").read_bytes() == runtime.read_bytes()
    assert (out / "eboot.bin").stat().st_ino == (game / "eboot.bin").stat().st_ino
