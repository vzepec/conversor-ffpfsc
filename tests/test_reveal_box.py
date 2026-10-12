from __future__ import annotations

import itertools

from ffpfsc_converter.ui.widgets.reveal_box import eased


def test_value_reaches_the_target_when_time_is_up() -> None:
    """Al cumplirse el tiempo (o pasarse) el valor es exactamente el final."""
    assert eased(0.0, 1.0, 1.0) == 1.0
    assert eased(1.0, 0.0, 1.7) == 0.0
    assert eased(1.0, 0.0, -0.5) == 1.0


def test_value_moves_monotonically_and_slows_down() -> None:
    """Avanza siempre hacia el final y los pasos se achican (desaceleración)."""
    values = [eased(0.0, 1.0, step / 10) for step in range(11)]
    steps = [b - a for a, b in itertools.pairwise(values)]
    assert values == sorted(values)
    assert steps[0] > steps[-1] >= 0
