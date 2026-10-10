"""Registro de la app en un archivo rotativo (para diagnosticar y reportar errores).

Se guarda junto a los ajustes, en la carpeta ``registros``: ``conversor.log`` y
hasta ``LOG_BACKUPS`` copias anteriores de ``LOG_MAX_BYTES`` cada una.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ffpfsc_converter.config import LOG_BACKUPS, LOG_MAX_BYTES
from ffpfsc_converter.infrastructure.settings_store import settings_path

LOGGER_NAME = "ffpfsc"
_FILE_NAME = "conversor.log"
_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"


def log_dir() -> Path:
    """Calcula la carpeta de los registros.

    Returns:
        Path: Carpeta ``registros`` junto al archivo de ajustes.
    """
    return settings_path().parent / "registros"


def setup_file_log(directory: Path) -> logging.Logger:
    """Configura el registro en archivo (una sola vez por proceso).

    Args:
        directory (Path): Carpeta de los registros (se crea si no existe).

    Returns:
        logging.Logger: Registro de la app; si no se pudo crear el archivo, queda
        sin destino y la app sigue funcionando.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / _FILE_NAME, maxBytes=LOG_MAX_BYTES,
                                      backupCount=LOG_BACKUPS, encoding="utf-8")
    except OSError:
        logger.addHandler(logging.NullHandler())
        return logger
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logger.info("Inicio en %s (Python %s)", sys.platform, sys.version.split()[0])
    return logger
