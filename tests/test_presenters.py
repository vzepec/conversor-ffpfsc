from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.config import PRESETS
from ffpfsc_converter.domain.models import (
    ConversionJob,
    ConversionResult,
    GameInfo,
    ProgressUpdate,
)
from ffpfsc_converter.ui import presenters


def test_format_size() -> None:
    """Formatea tamaños en base 1024 hasta TB."""
    assert presenters.format_size(512) == "512.0 B"
    assert presenters.format_size(1536) == "1.5 KB"
    assert presenters.format_size(5 * 1024**4) == "5.0 TB"
    assert presenters.format_size(2048 * 1024**4) == "2048.0 TB"


def test_game_info_text() -> None:
    """Muestra título, Title ID y versión cuando existen."""
    assert presenters.game_info_text(GameInfo()) == "(sin nombre)"
    assert presenters.game_info_text(GameInfo("G", "PPSA1", "1.0")) == "G  (PPSA1 · v1.0)"
    assert presenters.game_info_text(GameInfo("G", "", "")) == "G"


def test_savings_text_handles_growth() -> None:
    """Usa signo + cuando el archivo crece."""
    assert presenters.savings_text(100, 60) == "−40%"
    assert presenters.savings_text(100, 135) == "+35%"
    assert presenters.savings_text(0, 10) == "−0%"


def test_estimate_text() -> None:
    """Muestra la estimación o el texto de pendiente."""
    job = ConversionJob(Path("/a"), Path("/a"), Path("/a.ffpfsc"), size=1000, estimates={3: 250})
    assert presenters.estimate_text(job, 3) == "≈ 250.0 B (−75%)"
    assert presenters.estimate_text(job, 9) == presenters.PENDING_TEXT


def test_estimates_summary_uses_short_labels() -> None:
    """Resume la estimación con los nombres cortos de los modos."""
    job = ConversionJob(Path("/g"), Path("/g"), Path("/g.ffpfsc"), size=2048,
                        estimates={3: 1024, 9: 512})
    text = presenters.estimates_summary(job, PRESETS)
    assert text == (
        "Estimación g (2.0 KB): Máxima velocidad: ≈1.0 KB  |  Máxima compresión: ≈512.0 B"
    )


def test_progress_text() -> None:
    """Traduce la fase y agrega la velocidad si existe."""
    assert presenters.progress_text(ProgressUpdate(10, "compress", "1 MB/s")) == \
        "Comprimiendo: 10%  —  1 MB/s"
    assert presenters.progress_text(ProgressUpdate(10, "other")) == "other: 10%"


def test_result_text() -> None:
    """Formatea éxito, cancelación y error."""
    job = ConversionJob(Path("/g"), Path("/g"), Path("/g.ffpfsc"), size=1000)
    ok = ConversionResult(True, False, 120, output_size=500)
    assert presenters.result_text(job, ok) == "✔ 500.0 B (−50%) en 2.0 min"
    assert presenters.result_text(job, ConversionResult(False, True, 1)) == "✖ Cancelado"
    assert presenters.result_text(job, ConversionResult(False, False, 1, message="código 2")) == \
        "✖ Error (código 2)"


def test_source_display_name(tmp_path: Path) -> None:
    """Incluye la imagen encontrada dentro de una carpeta."""
    image = tmp_path / "inner.exfat"
    image.touch()
    job = ConversionJob(tmp_path, image, tmp_path / "x.ffpfsc")
    assert presenters.source_display_name(job) == f"{tmp_path.name}/inner.exfat"


def test_parse_dropped_item() -> None:
    """Decodifica URIs file:// y acepta rutas simples."""
    assert presenters.parse_dropped_item("file:///home/u/Mi%20Juego") == Path("/home/u/Mi Juego")
    assert presenters.parse_dropped_item("/plain/path") == Path("/plain/path")
