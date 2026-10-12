from __future__ import annotations

from pathlib import Path

import pytest

from ffpfsc_converter.config import FREE_SPACE_MARGIN
from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions, OutputFormat
from ffpfsc_converter.services import preflight


def _job(tmp_path: Path, size: int, estimates: dict[int, int]) -> ConversionJob:
    """Crea un trabajo ya analizado cuya salida está en ``tmp_path``."""
    return ConversionJob(tmp_path, tmp_path, tmp_path / "x.ffpfsc", size=size, estimates=estimates)


def test_unknown_size_skips_the_check(tmp_path: Path) -> None:
    """Sin tamaño conocido no se compara el espacio."""
    assert preflight.check_free_space(_job(tmp_path, 0, {}), ConversionOptions(3, 1, False)) is None


def test_uses_estimate_plus_margin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exige el peso estimado más el margen de seguridad."""
    monkeypatch.setattr(preflight, "free_space", lambda _d: 1000)
    check = preflight.check_free_space(_job(tmp_path, 5000, {3: 900}),
                                        ConversionOptions(3, 1, False))
    assert check == preflight.SpaceCheck(1000, int(900 * FREE_SPACE_MARGIN))
    assert check.is_enough


def test_falls_back_to_original_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin estimación para el nivel usa el tamaño original."""
    monkeypatch.setattr(preflight, "free_space", lambda _d: 1000)
    check = preflight.check_free_space(_job(tmp_path, 5000, {}), ConversionOptions(9, 1, False))
    assert check is not None and not check.is_enough


def test_performance_uses_its_own_estimate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Con «Rendimiento en la PS5» exige el peso estimado para ese modo (más grande)."""
    monkeypatch.setattr(preflight, "free_space", lambda _d: 1000)
    job = _job(tmp_path, 5000, {3: 900})
    job.performance_estimates = {3: 1200}
    check = preflight.check_free_space(job, ConversionOptions(3, 1, False, threshold_gain=20))
    assert check == preflight.SpaceCheck(1000, int(1200 * FREE_SPACE_MARGIN))


def test_lz4_on_the_same_disk_only_needs_the_packs(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """Con LZ4 en el mismo disco, lo suelto se enlaza: solo cuenta el peso de los paquetes."""
    monkeypatch.setattr(preflight, "free_space", lambda _d: 1000)
    job = _job(tmp_path, 5000, {})
    job.lz4_estimate, job.lz4_loose_bytes = 3000, 2500
    options = ConversionOptions(9, 1, False, output_format=OutputFormat.LZ4)
    check = preflight.check_free_space(job, options)
    assert check == preflight.SpaceCheck(1000, int(500 * FREE_SPACE_MARGIN))
    monkeypatch.setattr(preflight, "same_device", lambda _a, _b: False)
    assert preflight.check_free_space(job, options).needed == int(3000 * FREE_SPACE_MARGIN)
