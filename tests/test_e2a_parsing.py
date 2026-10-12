"""Tests de la conversión de respuestas JSON de exfat2ampr a modelos del dominio."""
from __future__ import annotations

from ffpfsc_converter.domain.lz4 import (
    EngineInfo,
    Lz4Compat,
    Lz4Destination,
    Lz4JobState,
    Lz4Source,
)
from ffpfsc_converter.infrastructure.exfat2ampr import parsing

FOLDER = {"type": "folder", "path": "/data/homebrew/PPSA01234", "title_id": "PPSA01234",
          "title": "Juego", "version": "01.000", "ampr": False, "partial": False,
          "selectable": True, "image": "x.png"}
IMAGE = {"type": "image", "path": "/mnt/usb0/homebrew/X.exfat", "smp_title": "PPSA05555",
         "title_id": "PPSA05555", "title": "Imagen", "version": "01.002", "extra": [1, 2]}


def test_parse_hello() -> None:
    """Lee la versión y el emparejamiento; sin campos, no está emparejado."""
    assert parsing.parse_hello({"paired": True, "local": False, "version": "1.45"}) == \
        EngineInfo("1.45", True)
    assert parsing.parse_hello({}) == EngineInfo("", False)


def test_parse_sources_folder_and_image() -> None:
    """Distingue carpetas e imágenes, conserva el Title ID de montaje e ignora campos extra."""
    folder, image = parsing.parse_sources([FOLDER, IMAGE])
    assert folder == Lz4Source("/data/homebrew/PPSA01234", "folder", "PPSA01234", "Juego",
                               "01.000")
    assert not folder.is_image
    assert image.is_image and image.smp_title == "PPSA05555"


def test_parse_sources_skips_invalid_items() -> None:
    """Omite elementos que no son objetos o que no tienen ruta."""
    items = [FOLDER, "texto", 3, {"title": "sin ruta"}, None]
    assert [s.path for s in parsing.parse_sources(items)] == [FOLDER["path"]]


def test_parse_destinations() -> None:
    """Usa ``path`` como base y tolera campos ausentes."""
    items = [
        {"path": "/data/homebrew", "mount": "/data", "kind": "internal", "index": -1,
         "label": "Internal storage", "fstype": "UFS", "total": 1000, "free": 400,
         "writable": True, "reason": "", "read_mbps": -1},
        {"path": "/mnt/usb0/homebrew", "kind": "usb", "index": 0, "writable": False,
         "reason": "read_only"},
        {"kind": "usb"},
    ]
    internal, usb = parsing.parse_destinations(items)
    assert internal == Lz4Destination("/data/homebrew", "internal", -1, "Internal storage",
                                      1000, 400, True, "")
    assert (usb.index, usb.free, usb.writable, usb.reason) == (0, 0, False, "read_only")


def test_parse_check_full() -> None:
    """Convierte errores y avisos a tuplas y la compatibilidad al enum."""
    check = parsing.parse_check({
        "title_id": "PPSA01234", "title": "Juego", "source_bytes": 100, "need_typical": 60,
        "need_max": 100, "dest_free": 50, "dest_total": 500, "compatible": "no",
        "errors": ["not_ampr", "space_insufficient"], "warnings": ["already_exists"],
    })
    assert check.compatible is Lz4Compat.NO
    assert check.errors == ("not_ampr", "space_insufficient")
    assert check.warnings == ("already_exists",)
    assert check.is_blocked
    assert (check.source_bytes, check.need_typical, check.dest_free) == (100, 60, 50)


def test_parse_check_defaults() -> None:
    """Sin campos: compatibilidad desconocida, sin errores y tamaños en cero."""
    check = parsing.parse_check({"compatible": "quizás", "errors": "no es lista"})
    assert check.compatible is Lz4Compat.UNKNOWN
    assert check.errors == () and check.warnings == ()
    assert not check.is_blocked
    assert parsing.parse_check({"compatible": "later"}).compatible is Lz4Compat.LATER


def test_parse_state_running() -> None:
    """Lee el avance, la velocidad, la cola y los flags del estado."""
    status = parsing.parse_state({
        "state": "running", "phase": "pack", "percent": 42, "bytes_done": 420,
        "bytes_total": 1000, "speed_bps": 1.5e6, "eta_seconds": 30, "code": "",
        "title_id": "PPSA01234", "title": "Juego", "dest": "/data/homebrew/PPSA01234",
        "waiting": 1, "resumable": "1", "queue": ["PPSA05555"], "runtime": {},
    })
    assert status.state is Lz4JobState.RUNNING and status.is_active
    assert (status.percent, status.bytes_done, status.eta_seconds) == (42, 420, 30)
    assert status.speed_bps == 1.5e6
    assert status.waiting and status.resumable
    assert status.queue == ("PPSA05555",)


def test_parse_state_unknown_and_missing_values() -> None:
    """Estado desconocido → idle; ETA negativa → None; porcentaje acotado a 0-100."""
    status = parsing.parse_state({"state": "rebooting", "eta_seconds": -1, "percent": 140,
                                  "speed_bps": True})
    assert status.state is Lz4JobState.IDLE and not status.is_active
    assert status.eta_seconds is None
    assert status.percent == 100
    assert status.speed_bps == 0.0
    assert parsing.parse_state({}).eta_seconds is None


def test_parse_state_terminal_states() -> None:
    """Reconoce todos los estados del motor."""
    for state in Lz4JobState:
        assert parsing.parse_state({"state": state.value}).state is state
