from __future__ import annotations

import pytest

from ffpfsc_converter.formatting import format_eta
from ffpfsc_converter.timing import EtaEstimator, PercentEta, SpeedAverage, remaining_seconds


class Clock:
    """Reloj manual para los tests."""

    def __init__(self) -> None:
        """Empieza en cero."""
        self.now = 0.0

    def __call__(self) -> float:
        """Devuelve la hora actual."""
        return self.now


def _feed(eta: EtaEstimator, clock: Clock, start: float, seconds: int, speed: float,
          done: float, total: float) -> tuple[float, float | None]:
    """Simula ``seconds`` segundos a velocidad constante; devuelve (hecho, último ETA)."""
    value = None
    for _ in range(seconds):
        clock.now += 1
        done += speed
        value = eta.update(done, total - done)
    return done, value


@pytest.mark.parametrize(("seconds", "text"), [
    (None, ""),
    (0.2, "quedan ≈ 1 s"),
    (45, "quedan ≈ 45 s"),
    (204, "quedan ≈ 3 min 20 s"),
    (1500, "quedan ≈ 25 min"),
    (3900, "quedan ≈ 1 h 05 min"),
])
def test_format_eta(seconds: float | None, text: str) -> None:
    """Formatea en s, en pasos de 10 s hasta 10 min, y luego en minutos u horas."""
    assert format_eta(seconds) == text


def test_speed_average_smooths() -> None:
    """La media móvil amortigua los picos de la velocidad mostrada."""
    average = SpeedAverage(smoothing=0.5)
    assert average.add(100) == 100
    assert average.add(200) == 150


def test_remaining_seconds() -> None:
    """Sin velocidad no hay estimación."""
    assert remaining_seconds(100, 20) == 5
    assert remaining_seconds(100, 0) is None


def test_eta_waits_for_warmup() -> None:
    """No informa nada durante los primeros segundos."""
    clock = Clock()
    eta = EtaEstimator(clock)
    _, value = _feed(eta, clock, 0, 3, 10, 0, 1000)
    assert value is None


def test_short_spike_barely_moves_the_eta() -> None:
    """Un pico de 2 s al triple de velocidad apenas cambia el ETA mostrado."""
    clock = Clock()
    eta = EtaEstimator(clock)
    done, before = _feed(eta, clock, 0, 20, 10, 0, 10_000)
    done, after = _feed(eta, clock, 0, 2, 30, done, 10_000)
    assert before is not None and after is not None
    assert after == pytest.approx(before - 2, abs=1)  # sigue la cuenta regresiva


def test_eta_counts_down_between_refreshes() -> None:
    """Entre recálculos el ETA baja segundo a segundo."""
    clock = Clock()
    eta = EtaEstimator(clock)
    done, first = _feed(eta, clock, 0, 10, 10, 0, 10_000)
    done, second = _feed(eta, clock, 0, 3, 10, done, 10_000)
    assert first is not None and second == pytest.approx(first - 3, abs=0.5)


def test_sustained_slowdown_updates_the_eta() -> None:
    """Si la velocidad baja a la mitad de forma sostenida, el ETA se corrige."""
    clock = Clock()
    eta = EtaEstimator(clock)
    done, fast = _feed(eta, clock, 0, 30, 20, 0, 20_000)
    done, slow = _feed(eta, clock, 0, 40, 10, done, 20_000)
    assert fast is not None and slow is not None
    assert slow == pytest.approx((20_000 - done) / 10, rel=0.3)


def test_percent_eta_resets_on_new_phase() -> None:
    """Al cambiar de fase de MkPFS la medición empieza de nuevo."""
    clock = Clock()
    eta = PercentEta(clock)
    for percent in range(0, 40, 4):
        clock.now += 1
        last = eta.update("compress", percent)
    assert last is not None
    clock.now += 1
    assert eta.update("write", 5) is None
