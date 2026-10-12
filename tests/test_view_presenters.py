from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.domain.pipeline import PipelineResult, PipelineStage, ReplacePlan
from ffpfsc_converter.domain.remote import DownloadResult, RemoteEntry, StorageVolume
from ffpfsc_converter.ui.explorer import transfer_presenters as tp
from ffpfsc_converter.ui.explorer import view_presenters as vp
from ffpfsc_converter.ui.explorer.presenters import replace_summary
from ffpfsc_converter.ui.widgets.text_fit import elide

GB = 1024**3


def _entry(name: str, is_dir: bool = False, folder: str = "/data/homebrew") -> RemoteEntry:
    """Crea un elemento remoto de prueba."""
    return RemoteEntry(name, f"{folder}/{name}", is_dir)


def test_entry_badge() -> None:
    """Clasifica juegos, imágenes y comprimidos; el resto no lleva etiqueta."""
    assert vp.entry_badge(_entry("Astro Bot", True)) == vp.Badge("Juego", "wait")
    assert vp.entry_badge(_entry("Juego PPSA01234", True, "/mnt/usb0")).text == "Juego"
    assert vp.entry_badge(_entry("etc", True, "/data")) is None
    assert vp.entry_badge(_entry("gt7.ffpfsc")) == vp.Badge("Comprimido", "ok")
    assert vp.entry_badge(_entry("Returnal.EXFAT")) == vp.Badge("Imagen", "warn")
    assert vp.entry_badge(_entry("notas.txt")) is None


def test_path_crumbs() -> None:
    """Divide la ruta en tramos que llevan a cada carpeta."""
    assert vp.path_crumbs("/") == []
    assert vp.path_crumbs("/data/homebrew") == [("data", "/data"),
                                                 ("homebrew", "/data/homebrew")]


def test_drive_cards() -> None:
    """Pone el interno primero, marca el disco lleno y agrega las ranuras vacías."""
    internal = StorageVolume("/data", "/dev/ssd0", 100 * GB, 10 * GB)
    usb = StorageVolume("/mnt/usb0", "/dev/da0", 100 * GB, 80 * GB)
    cards = vp.drive_cards([usb, internal], connected=True)
    assert [c.name for c in cards] == ["Interno", "USB 1", "Ampliado"]
    assert cards[0].is_full and cards[0].percent == 90.0
    assert cards[0].text == "10.0 GB libres de 100.0 GB"
    assert not cards[1].is_full
    assert cards[2] == vp.DriveCard("Ampliado", "/mnt/ext0", "drive", 0.0, "No conectado",
                                    False, False)
    offline = vp.drive_cards([], connected=False)
    assert [c.text for c in offline] == ["Sin conexión"] * 3


def test_internal_free_text() -> None:
    """Resume el espacio libre del disco interno, si se conoce."""
    internal = StorageVolume("/data", "/dev/ssd0", 100 * GB, 10 * GB)
    assert vp.internal_free_text([internal]) == "10.0 GB libres en /data"
    assert vp.internal_free_text([]) == ""


def test_selection_and_actions() -> None:
    """Describe la selección y habilita solo las acciones que aplican."""
    assert vp.selection_text(0) == "Nada seleccionado"
    assert vp.selection_text(1) == "1 seleccionado"
    assert vp.selection_text(3) == "3 seleccionados"
    game, text = _entry("Juego", True), _entry("notas.txt")
    assert vp.action_states(True, False, [game]) == vp.ActionStates(True, True, True, True)
    assert vp.action_states(True, False, [text]).convert is False
    assert vp.action_states(True, False, [game, game]).convert is False
    assert vp.action_states(True, False, []) == vp.ActionStates(False, False, True, False)
    assert vp.action_states(False, False, [game]) == vp.ActionStates(False, False, False, False)


def test_writing_pauses_actions_but_keeps_connection() -> None:
    """Mientras se escribe en la PS5 se pausan las acciones y se explica por qué."""
    game = _entry("Juego", True)
    assert vp.action_states(True, True, [game]) == vp.ActionStates(False, False, False, False)
    assert "Escribiendo en la PS5" in vp.selection_text(1, writing=True)


def test_transfer_texts() -> None:
    """Formatea el avance y el resultado de una descarga."""
    assert tp.transfer_progress(512, 2048) == (25.0, "25% · 512.0 B de 2.0 KB")
    assert tp.transfer_progress(0, 0).percent == 0.0
    ok = tp.download_result_status(DownloadResult(True, False, 12, files=3))
    assert ok == ("ok", "✓ Descargado", "3 archivo(s) en 12 s")
    assert tp.download_result_status(DownloadResult(False, True, 1)).kind == "warn"
    failed = DownloadResult(False, False, 1, message="Sin espacio\n\ndetalle")
    assert tp.download_result_status(failed) == ("bad", "Error", "Sin espacio")


def test_destination_text() -> None:
    """Abrevia la carpeta personal y avisa si aún no hay carpeta."""
    home = Path("/home/v")
    assert tp.destination_text(home / "PS5", home) == f"Descargar en {Path('~') / 'PS5'}"
    assert tp.destination_text(Path("/media/disco"), home) == \
        f"Descargar en {Path('/media/disco')}"
    assert tp.destination_text(None, home) == "Sin carpeta de descargas"


class _Monospace:
    """Fuente de prueba: cada carácter mide 10 px."""

    def measure(self, text: str) -> int:
        """Mide el texto a 10 px por carácter."""
        return 10 * len(text)


def test_elide() -> None:
    """Deja el texto si cabe y, si no, lo recorta con puntos suspensivos."""
    assert elide("corto", _Monospace(), 50) == "corto"
    assert elide("muy largo", _Monospace(), 50) == "muy …"
    assert elide("abc", _Monospace(), 5) == "…"


def test_pipeline_row_texts() -> None:
    """Describe el paso, limita el porcentaje y resume el resultado del reemplazo."""
    assert tp.pipeline_step_text(PipelineStage.COMPRESS) == "Paso 2 de 3 · Comprimiendo"
    assert tp.pipeline_step_text(PipelineStage.DOWNLOAD).startswith("Paso 1 de 3")
    assert tp.pipeline_progress(101.4, "1 GB de 1 GB") == (100.0, "100% · 1 GB de 1 GB")
    assert tp.pipeline_progress(5, "").text == "5%"
    assert tp.pipeline_result_status(PipelineResult(True, False, "listo")) == (
        "ok", "✓ Reemplazado", "listo")
    assert tp.pipeline_result_status(PipelineResult(False, True, "x")).kind == "warn"
    assert tp.pipeline_result_status(PipelineResult(False, False, "falló")).kind == "bad"


def test_replace_summary_shows_exact_paths() -> None:
    """El resumen nombra las rutas exactas; con LZ4 la carpeta ocupa el lugar del original."""
    game = RemoteEntry("Juego", "/data/homebrew/Juego", True)
    ffpfsc = ReplacePlan(game, "/data/homebrew/Juego.ffpfsc", "/data/homebrew/Juego.ffpfsc.part",
                         True)
    text = replace_summary(ffpfsc, is_lz4=False)
    assert "/data/homebrew/Juego.ffpfsc" in text and "BORRARÁ" in text
    assert "Ya existe" in text and text.endswith("antes de continuar.")
    lz4 = ReplacePlan(game, game.path, game.path + ".part", False)
    assert replace_summary(lz4, is_lz4=True).startswith(
        "La carpeta LZ4 reemplazará a /data/homebrew/Juego ")
