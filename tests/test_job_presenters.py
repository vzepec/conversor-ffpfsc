from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.domain.models import (
    ConversionJob,
    ConversionResult,
    GameInfo,
    ProgressUpdate,
)
from ffpfsc_converter.ui import job_presenters as jp
from ffpfsc_converter.ui.presenters import ConsoleStatus, connection_card, connection_pill


def _job(size: int = 0, estimates: dict[int, int] | None = None) -> ConversionJob:
    """Crea un trabajo de prueba con tamaño y estimaciones opcionales."""
    return ConversionJob(Path("/g"), Path("/g"), Path("/g.ffpfsc"), size=size,
                         estimates=estimates or {})


def test_game_title_and_meta() -> None:
    """Usa el Title ID y la versión, o el texto de respaldo si no hay datos."""
    info = GameInfo("Juego", "PPSA01234", "01.002")
    assert jp.game_title(info) == "Juego"
    assert jp.game_title(GameInfo()) == "(sin nombre)"
    assert jp.game_meta(info, "carpeta") == "PPSA01234 · v01.002"
    assert jp.game_meta(GameInfo(), "carpeta") == "carpeta"


def test_size_lines_follow_analysis() -> None:
    """Muestra «calculando», luego el tamaño y por último la estimación con el ahorro."""
    assert jp.size_lines(_job(), 3) == ("calculando…", "", "")
    assert jp.size_lines(_job(1000), 3) == ("1000.0 B", "", "estimando…")
    assert jp.size_lines(_job(1000, {3: 250}), 3) == ("1000.0 B →", "≈ 250.0 B", "−75% estimado")


def test_progress_status() -> None:
    """Traduce la fase y une velocidad y tiempo restante en el detalle."""
    status = jp.progress_status(ProgressUpdate(37, "compress", "1 MB/s"), None)
    assert status == jp.RowStatus("run", "Comprimiendo · 37%", "1 MB/s")
    assert jp.progress_status(ProgressUpdate(5, "other"), None).label == "other · 5%"


def test_result_status() -> None:
    """Distingue éxito, cancelación y error con su motivo."""
    job = _job(1000)
    ok = jp.result_status(job, ConversionResult(True, False, 120, output_size=500))
    assert ok == jp.RowStatus("ok", "✓ Listo", "500.0 B (−50%) en 2.0 min")
    assert jp.result_status(job, ConversionResult(False, True, 1)).kind == "warn"
    error = jp.result_status(job, ConversionResult(False, False, 1, message="código 2"))
    assert error == jp.RowStatus("bad", "Error", "código 2")


def test_upload_status() -> None:
    """Calcula el porcentaje de la subida y tolera archivos vacíos."""
    status, percent = jp.upload_status(25, 100, "10 MB/s", None)
    assert percent == 25.0
    assert status == jp.RowStatus("run", "Subiendo a la PS5 · 25%", "10 MB/s")
    assert jp.upload_status(0, 0, "", None)[1] == 100.0


def test_queue_summary() -> None:
    """Resume la cola y solo suma estimaciones cuando todas están listas."""
    assert jp.queue_summary([], 3) == ""
    assert jp.queue_summary([_job(1000)], 3) == "1 juego"
    jobs = [_job(1000, {3: 400}), _job(1000, {3: 100})]
    assert jp.queue_summary(jobs, 3) == "2 juegos  ·  2.0 KB → ≈ 500.0 B"


def test_connection_card() -> None:
    """Resume la conexión con la PS5 para la barra lateral."""
    assert connection_card(ConsoleStatus(False, "", False, "")).state == "off"
    assert connection_card(ConsoleStatus(False, "", True, "10.0.0.2")).title == "Conectando…"
    idle = connection_card(ConsoleStatus(True, "", False, "10.0.0.2", "66.9 GB libres en /data"))
    assert (idle.state, idle.lines) == ("on", ("10.0.0.2 · solo lectura",
                                               "66.9 GB libres en /data"))
    busy = connection_card(ConsoleStatus(True, "Subiendo…", True, "10.0.0.2"))
    assert (busy.state, busy.lines) == ("busy", ("Subiendo…",))


def test_connection_pill() -> None:
    """Muestra el modo del FTP, la operación en curso o cómo empezar."""
    assert connection_pill(ConsoleStatus(True, "", False, "ip")) == ("wait", "FTP en solo lectura")
    assert connection_pill(ConsoleStatus(True, "Eliminando…", True, "ip")) == (
        "run", "Eliminando…")
    assert connection_pill(ConsoleStatus(False, "", False, "")).label == "Escribe la IP de la PS5"
    assert connection_pill(ConsoleStatus(False, "Sin conexión.", False, "ip")) is None
