from __future__ import annotations

from ffpfsc_converter.ui.widgets.flow_frame import flow_rows


def test_everything_fits_in_one_line() -> None:
    """Si hay espacio, todos los elementos quedan en la primera línea."""
    assert flow_rows([300, 100, 150], available=600, gap=20) == [0, 0, 0]


def test_wraps_when_the_next_item_does_not_fit() -> None:
    """El elemento que no cabe (contando la separación) pasa a la línea siguiente."""
    assert flow_rows([300, 100, 150, 150], available=600, gap=20) == [0, 0, 0, 1]
    assert flow_rows([300, 100, 150], available=589, gap=20) == [0, 0, 1]


def test_item_wider_than_container_takes_its_own_line() -> None:
    """Un elemento más ancho que el contenedor no deja líneas vacías."""
    assert flow_rows([700, 100], available=600, gap=20) == [0, 1]
    assert flow_rows([], available=600, gap=20) == []
