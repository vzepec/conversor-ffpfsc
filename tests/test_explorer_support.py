from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.domain.remote import DownloadJob, DownloadResult, RemoteEntry
from ffpfsc_converter.domain.remote_events import DownloadProgress
from ffpfsc_converter.infrastructure import settings_store
from ffpfsc_converter.infrastructure.ava1.trust import TrustStore
from ffpfsc_converter.services.progress_meter import ProgressMeter
from ffpfsc_converter.ui.explorer import presenters

FILE = RemoteEntry("juego.ffpfsc", "/data/homebrew/juego.ffpfsc", False, 2048, "20261009153000")
FOLDER = RemoteEntry("homebrew", "/data/homebrew", True)


def test_entry_texts() -> None:
    """Muestra icono, tamaño y fecha legibles."""
    assert presenters.entry_label(FOLDER) == "📁 homebrew"
    assert presenters.entry_label(FILE) == "📄 juego.ffpfsc"
    assert presenters.entry_size_text(FILE) == "2.0 KB"
    assert presenters.entry_size_text(FOLDER) == ""
    assert presenters.modified_text(FILE.modified) == "2026-10-09 15:30"
    assert presenters.modified_text("") == ""


def test_parent_path() -> None:
    """Sube un nivel sin pasar de la raíz."""
    assert presenters.parent_path("/data/homebrew") == "/data"
    assert presenters.parent_path("/data") == "/"
    assert presenters.parent_path("/") == "/"


def test_progress_and_results() -> None:
    """Formatea porcentaje, velocidad y resultados."""
    job = DownloadJob(FILE, Path("/tmp"), total_bytes=4096, done_bytes=1024)
    assert presenters.progress_text(job) == "25%  (1.0 KB de 4.0 KB)"
    assert presenters.speed_text(0) == ""
    assert presenters.speed_text(2 * 1024 * 1024) == "2.0 MB/s"
    assert presenters.download_result_text(DownloadResult(True, False, 12, files=3)) == \
        "✔ 3 archivo(s) en 12 s"
    assert "reanudar" in presenters.download_result_text(DownloadResult(False, True, 1))
    failed = DownloadResult(False, False, 1, message="Sin espacio\n\ndetalle")
    assert presenters.download_result_text(failed) == "✖ Error: Sin espacio"


def test_progress_meter_throttles() -> None:
    """Publica como máximo una vez por intervalo y calcula la velocidad."""
    now = [0.0]
    events: list[object] = []
    job = DownloadJob(FILE, Path("/tmp"))
    meter = ProgressMeter(job, events.append, interval=1.0, clock=lambda: now[0])
    meter.skip(100)
    meter.advance(50, "a")
    assert events == []
    now[0] = 2.0
    meter.advance(150, "a")
    assert job.done_bytes == 300
    assert events == [DownloadProgress(job, "a", 100.0)]


def test_settings_path_per_platform(tmp_path: Path) -> None:
    """Usa %APPDATA% en Windows y XDG o ~/.config en Linux."""
    win = settings_store.settings_path("win32", {"APPDATA": "C:/Users/v/AppData/Roaming"})
    assert win == Path("C:/Users/v/AppData/Roaming/ffpfsc-converter/settings.json")
    xdg = settings_store.settings_path("linux", {"XDG_CONFIG_HOME": "/x"})
    assert xdg == Path("/x/ffpfsc-converter/settings.json")
    assert settings_store.settings_path("linux", {}, tmp_path) == \
        tmp_path / ".config" / "ffpfsc-converter" / "settings.json"


def test_settings_round_trip_and_corruption(tmp_path: Path) -> None:
    """Fusiona ajustes y tolera un archivo dañado."""
    path = tmp_path / "s.json"
    settings_store.save_settings({"a": 1}, path)
    settings_store.save_settings({"b": "dos"}, path)
    assert settings_store.load_settings(path) == {"a": 1, "b": "dos"}
    path.write_text("{roto")
    assert settings_store.load_settings(path) == {}


def test_trust_store(tmp_path: Path) -> None:
    """Crea la identidad una vez (privada) y recuerda consolas."""
    store = TrustStore(tmp_path)
    first = store.identity().private_bytes_raw()
    assert store.identity().private_bytes_raw() == first
    assert (tmp_path / "ava1_identity.key").stat().st_mode & 0o077 == 0
    assert store.known_key("10.0.0.5") is None
    store.remember("10.0.0.5", b"\x01" * 32, "PS5")
    assert TrustStore(tmp_path).known_key("10.0.0.5") == b"\x01" * 32
