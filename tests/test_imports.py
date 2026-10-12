from __future__ import annotations

import importlib
import pkgutil

import pytest

import ffpfsc_converter

MODULES = sorted(info.name for info in pkgutil.walk_packages(
    ffpfsc_converter.__path__, f"{ffpfsc_converter.__name__}."))


@pytest.mark.parametrize("name", MODULES)
def test_every_module_imports(name: str) -> None:
    """Cada módulo se importa sin errores (detecta imports de módulos borrados)."""
    importlib.import_module(name)
