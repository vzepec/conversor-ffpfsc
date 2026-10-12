from __future__ import annotations

import itertools

from ffpfsc_converter.ui.widgets.collapsible import eased_height


def test_height_reaches_the_target_when_time_is_up() -> None:
    """Al cumplirse el tiempo (o pasarse) el alto es exactamente el final."""
    assert eased_height(0, 80, 1.0) == 80
    assert eased_height(80, 0, 1.7) == 0
    assert eased_height(80, 0, -0.5) == 80


def test_height_moves_monotonically_and_slows_down() -> None:
    """El alto avanza siempre hacia el final y los pasos se achican (desaceleración)."""
    heights = [eased_height(0, 100, step / 10) for step in range(11)]
    steps = [b - a for a, b in itertools.pairwise(heights)]
    assert heights == sorted(heights)
    assert steps[0] > steps[-1] >= 0
