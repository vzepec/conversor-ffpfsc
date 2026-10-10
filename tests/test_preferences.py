from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.ui.preferences import convert_from, window_from

PRESETS = ("Máxima velocidad", "Equilibrado")


def test_convert_preferences_are_validated(tmp_path: Path) -> None:
    """Recupera lo guardado y descarta valores inválidos o carpetas que ya no existen."""
    saved = {"convert_preset": "Equilibrado", "convert_cores": 64, "convert_verify": True,
             "output_dir": str(tmp_path)}
    prefs = convert_from(saved, PRESETS, cpu_total=8)
    assert (prefs.preset, prefs.cores, prefs.full_verify) == ("Equilibrado", 8, True)
    assert prefs.output_dir == tmp_path
    odd = convert_from({"convert_preset": "Turbo", "convert_cores": "x",
                        "output_dir": str(tmp_path / "borrada")}, PRESETS, cpu_total=8)
    assert (odd.preset, odd.cores, odd.full_verify, odd.output_dir) == (None, None, False, None)


def test_window_preferences_fit_the_screen() -> None:
    """Solo recupera un tamaño que quepa en la pantalla y una vista que exista."""
    views = ("convert", "ps5")
    ok = window_from({"window_size": [1200, 800], "window_zoomed": True, "last_view": "ps5"},
                     (1000, 600), (1920, 1080), views)
    assert (ok.size, ok.zoomed, ok.view) == ((1200, 800), True, "ps5")
    too_big = window_from({"window_size": [4000, 800], "last_view": "otra"}, (1000, 600),
                          (1920, 1080), views)
    assert (too_big.size, too_big.zoomed, too_big.view) == (None, False, "convert")
    assert window_from({}, (1000, 600), (1920, 1080), views).size is None
