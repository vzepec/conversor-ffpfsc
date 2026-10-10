from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from ffpfsc_converter.domain.events import QueueFinished
from ffpfsc_converter.domain.pipeline import PipelineResult
from ffpfsc_converter.domain.pipeline_events import PipelineFinished
from ffpfsc_converter.domain.remote import ConsoleTarget
from ffpfsc_converter.domain.remote_events import RemoteConnected, RemoteError
from ffpfsc_converter.infrastructure.app_log import LOGGER_NAME, setup_file_log
from ffpfsc_converter.ui.event_journal import JournalEntry, journal_line


@pytest.fixture
def clean_logger() -> Iterator[logging.Logger]:
    """Deja el registro de la app sin destinos antes y después de cada prueba."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    yield logger
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()


def test_file_log_writes_and_is_configured_once(tmp_path: Path,
                                                clean_logger: logging.Logger) -> None:
    """Crea la carpeta y el archivo, y no duplica destinos si se configura dos veces."""
    logger = setup_file_log(tmp_path / "registros")
    setup_file_log(tmp_path / "registros")
    logger.warning("prueba de registro")
    for handler in logger.handlers:
        handler.flush()
    text = (tmp_path / "registros" / "conversor.log").read_text(encoding="utf-8")
    assert "Inicio en" in text and "prueba de registro" in text
    assert len(clean_logger.handlers) == 1


def test_journal_lines() -> None:
    """Registra conexiones, errores y resultados; el avance no se registra."""
    target = ConsoleTarget("10.0.0.2", 2122)
    assert journal_line(RemoteConnected(target)) == JournalEntry(
        logging.INFO, "PS5 RemoteConnected: 10.0.0.2:2122")
    assert journal_line(RemoteError("sin red")) == JournalEntry(logging.WARNING, "PS5: sin red")
    failed = journal_line(PipelineFinished(PipelineResult(False, False, "falló")))
    assert failed is not None and failed.level == logging.ERROR
    assert journal_line(QueueFinished(cancelled=False)).level == logging.INFO  # type: ignore[union-attr]
    assert journal_line(object()) is None
