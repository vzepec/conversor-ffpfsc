from __future__ import annotations

from pathlib import Path

import pytest

from ffpfsc_converter.config import FREE_SPACE_MARGIN
from ffpfsc_converter.domain.models import ConversionJob
from ffpfsc_converter.services import preflight


def _job(tmp_path: Path, size: int, estimates: dict[int, int]) -> ConversionJob:
    """Crea un trabajo ya analizado cuya salida está en ``tmp_path``."""
    return ConversionJob(tmp_path, tmp_path, tmp_path / "x.ffpfsc", size=size, estimates=estimates)


def test_unknown_size_skips_the_check(tmp_path: Path) -> None:
    """Sin tamaño conocido no se compara el espacio."""
    assert preflight.check_free_space(_job(tmp_path, 0, {}), 3) is None


def test_uses_estimate_plus_margin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exige el peso estimado más el margen de seguridad."""
    monkeypatch.setattr(preflight, "free_space", lambda _d: 1000)
    check = preflight.check_free_space(_job(tmp_path, 5000, {3: 900}), 3)
    assert check == preflight.SpaceCheck(1000, int(900 * FREE_SPACE_MARGIN))
    assert check.is_enough


def test_falls_back_to_original_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin estimación para el nivel usa el tamaño original."""
    monkeypatch.setattr(preflight, "free_space", lambda _d: 1000)
    check = preflight.check_free_space(_job(tmp_path, 5000, {}), 9)
    assert check is not None and not check.is_enough
