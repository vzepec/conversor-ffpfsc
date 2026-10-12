from __future__ import annotations

import logging

from ffpfsc_converter.domain.lz4 import (
    Lz4Check,
    Lz4Compat,
    Lz4Destination,
    Lz4JobState,
    Lz4Request,
    Lz4Source,
    Lz4Status,
)
from ffpfsc_converter.domain.lz4_events import Lz4Finished, Lz4PairingRequired, Lz4Started
from ffpfsc_converter.ui.event_journal import journal_line
from ffpfsc_converter.ui.explorer import lz4_presenters as lp
from ffpfsc_converter.ui.explorer import lz4_status_presenters as sp
from ffpfsc_converter.ui.explorer import lz4_target_presenters as tp
from ffpfsc_converter.ui.notifications import Notification, notification_for

GB = 1024**3
_SOURCE = Lz4Source("/data/homebrew/PPSA01234", "folder", "PPSA01234", "Astro Bot", "01.000")


def _check(errors: tuple[str, ...] = (), warnings: tuple[str, ...] = (),
           compat: Lz4Compat = Lz4Compat.YES) -> Lz4Check:
    """Crea una comprobación previa de prueba."""
    return Lz4Check("PPSA01234", "Astro Bot", 48 * GB, 30 * GB, 48 * GB, 100 * GB, 900 * GB,
                    compat, errors, warnings)


def _request(dest: str = "/data/homebrew", remove: bool = False,
             overwrite: bool = False) -> Lz4Request:
    """Crea una conversión de prueba."""
    return Lz4Request(_SOURCE, dest, 9, True, remove, overwrite)


def _dest(kind: str, index: int, free: int = 180 * GB) -> Lz4Destination:
    """Crea una unidad de destino de prueba."""
    return Lz4Destination(f"/mnt/{kind}{index}/homebrew", kind, index, "Label", 1000 * GB, free,
                          True)


def test_compat_texts() -> None:
    """Explica la compatibilidad y solo impide empezar si no es compatible."""
    assert lp.compat_info(Lz4Compat.YES).kind == "ok"
    assert lp.compat_info(Lz4Compat.UNKNOWN).can_start is True
    assert "al empezar" in lp.compat_info(Lz4Compat.LATER).text
    assert lp.compat_info(Lz4Compat.NO) == lp.CompatInfo("bad", lp.compat_info(Lz4Compat.NO).text,
                                                         False)


def test_check_codes_are_translated() -> None:
    """Traduce errores y avisos de /api/check; los desconocidos muestran el código."""
    assert "ciérralo" in lp.check_error_text("game_running")
    assert "raro" in lp.check_error_text("raro")
    lines = lp.warning_lines(_check(warnings=("space_low", "ampr_unknown", "nuevo")))
    assert len(lines) == 2 and "pausa" in lines[0] and "nuevo" in lines[1]


def test_start_blockers_depend_on_destination() -> None:
    """Los errores de espacio solo aplican al destino comprobado; los del juego, siempre."""
    check = _check(errors=("space_insufficient", "game_running"))
    same = lp.start_blockers(check, "/data/homebrew/", _request("/data/homebrew"))
    other = lp.start_blockers(check, "/data/homebrew", _request("/mnt/usb0/homebrew"))
    assert len(same) == 2 and len(other) == 1 and "ciérralo" in other[0]
    assert lp.start_blockers(_check(), "/data/homebrew", _request()) == []


def test_incompatible_game_cannot_start() -> None:
    """Un juego no compatible no se puede iniciar aunque no venga el código de error."""
    blockers = lp.start_blockers(_check(compat=Lz4Compat.NO), "/data/homebrew", _request())
    assert blockers == [lp.compat_info(Lz4Compat.NO).text]


def test_existing_output_needs_overwrite() -> None:
    """Si ya existe la conversión en el destino, hay que activar el reemplazo."""
    check = _check(warnings=(lp.ALREADY_EXISTS,))
    assert lp.replaces_existing(check, "/data/homebrew", "/data/homebrew") is True
    assert lp.replaces_existing(check, "/data/homebrew", "/mnt/usb0/homebrew") is False
    assert lp.start_blockers(check, "/data/homebrew", _request()) == [lp.OVERWRITE_NEEDED_TEXT]
    assert lp.start_blockers(check, "/data/homebrew", _request(overwrite=True)) == []


def test_rejection_and_game_texts() -> None:
    """Enumera los motivos del rechazo y resume el juego y su tamaño."""
    text = lp.rejection_text(_check(errors=("not_ampr", "dest_readonly")))
    assert text.count("•") == 2 and "libSceAmpr" in text
    assert lp.game_text(_SOURCE) == "Astro Bot · PPSA01234 · versión 01.000"
    untitled = Lz4Source("/x", "image", "PPSA01234", "", "")
    assert lp.game_text(untitled) == "PPSA01234"
    assert lp.size_text(_check()) == "Juego: 48.0 GB · necesita ≈ 30.0 GB (hasta 48.0 GB)"


def test_destination_labels() -> None:
    """Nombra las unidades como la PS5 y muestra su espacio libre."""
    internal = Lz4Destination("/data/homebrew", "internal", -1, "Internal", 800 * GB, 180 * GB,
                              True)
    assert tp.destination_label(internal) == "Interno · 180.0 GB libres"
    assert tp.destination_name(_dest("usb", 0)) == "USB 1"
    assert tp.destination_name(_dest("usb", 1)) == "USB 2"
    assert tp.destination_name(_dest("extended", 0)) == "Ampliado"
    assert tp.destination_name(_dest("extended", 1)) == "Ampliado 2"
    odd = Lz4Destination("/otra", "raro", 0, "Network", 1, 1, True)
    assert tp.destination_name(odd) == "Network"
    blocked = Lz4Destination("/mnt/usb1/homebrew", "usb", 1, "", 1, 0, False, "read_only")
    assert tp.writable_destinations([internal, blocked]) == [internal]


def test_summary_shows_exact_paths() -> None:
    """El resumen muestra la carpeta que se crea y, si se pide, la que se BORRARÁ."""
    keep = tp.summary_lines(_request(), replaces=False)
    assert keep[0] == "Se creará /data/homebrew/PPSA01234" and "conserva" in keep[1]
    remove = tp.summary_lines(_request(remove=True, overwrite=True), replaces=True)
    assert remove[0] == "Se REEMPLAZARÁ /data/homebrew/PPSA01234"
    assert remove[1] == "Se BORRARÁ de la PS5 al terminar bien: /data/homebrew/PPSA01234"
    question = tp.remove_confirmation(_request("/mnt/usb0/homebrew", remove=True))
    assert "/data/homebrew/PPSA01234" in question and "/mnt/usb0/homebrew/PPSA01234" in question


def test_pairing_text() -> None:
    """Indica dónde ver el código y avisa si el anterior fue incorrecto."""
    assert "http://10.0.0.2:6972/" in tp.pairing_text("10.0.0.2", retry=False)
    assert tp.pairing_text("10.0.0.2", retry=True).startswith("El código no era correcto")


def test_row_texts() -> None:
    """Prepara la fase, la barra y la cola de la fila."""
    running = Lz4Status(Lz4JobState.RUNNING, "pack", 42, 20 * GB, 48 * GB, title="Astro Bot")
    assert sp.row_subtitle(running) == "LZ4 en la PS5 · Comprimiendo (LZ4)"
    assert sp.row_subtitle(Lz4Status(Lz4JobState.DONE, "done")) == sp.ROW_SUBTITLE
    assert sp.row_progress(running) == (42.0, "42% · 20.0 GB de 48.0 GB")
    assert sp.row_progress(Lz4Status(Lz4JobState.RUNNING, percent=150)) == (100.0, "100%")
    assert sp.phase_text("nueva") == "nueva"
    assert sp.queued_text(0) == sp.STARTING_TEXT and "2 por delante" in sp.queued_text(2)
    assert sp.job_name(running) == "Astro Bot"
    assert sp.job_name(Lz4Status(Lz4JobState.RUNNING)) == "exfat2ampr"


def test_result_status() -> None:
    """Resume el resultado: terminado, cancelado, en pausa o con error."""
    done = Lz4Status(Lz4JobState.DONE, code="done_fakelib", dest="/data/homebrew/PPSA01234")
    ok = sp.result_status(done)
    assert ok.kind == "ok" and ok.detail.startswith("Quedó en /data/homebrew/PPSA01234.")
    assert "Emuladores" in ok.detail
    assert sp.result_status(Lz4Status(Lz4JobState.CANCELLED)).kind == "warn"
    paused = Lz4Status(Lz4JobState.PAUSED, code="paused_full", dest="/d/X", resumable=True)
    assert sp.result_status(paused).detail == sp.code_text("paused_full", "")
    assert sp.can_resume(paused) and not sp.can_resume(done)
    failed = sp.result_status(Lz4Status(Lz4JobState.ERROR, code="not_ampr"))
    assert failed.kind == "bad" and "libSceAmpr" in failed.detail
    assert "disk on fire" in sp.code_text("raro", "disk on fire")
    assert sp.failed_status("\nSin red.\nMás") == ("bad", "Error", "Sin red.")
    assert "/d/X" in sp.cancel_confirmation("/d/X")


def test_finish_notification_and_journal() -> None:
    """Avisa al terminar (no si se canceló) y registra el resultado sin datos sensibles."""
    done = Lz4Status(Lz4JobState.DONE, dest="/data/homebrew/PPSA01234")
    assert notification_for(Lz4Finished("h", done)) == Notification(
        "Compresión LZ4 terminada en la PS5", "Quedó en /data/homebrew/PPSA01234.")
    assert notification_for(Lz4Finished("h", Lz4Status(Lz4JobState.CANCELLED))) is None
    error = journal_line(Lz4Finished("h", Lz4Status(Lz4JobState.ERROR, code="verify_failed")))
    assert error is not None and error.level == logging.ERROR
    started = journal_line(Lz4Started("h", _request(), 0))
    assert started is not None and "/data/homebrew/PPSA01234" in started.text
    pairing = journal_line(Lz4PairingRequired("h", "/data/homebrew/PPSA01234", retry=True))
    assert pairing is not None and pairing.level == logging.INFO
