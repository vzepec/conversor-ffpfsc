from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import check_standards  # noqa: E402 - depende de la ruta agregada arriba


def _module(tmp_path: Path, source: str) -> Path:
    """Escribe un módulo Python en ``src/`` de un repositorio temporal."""
    path = tmp_path / "src" / "mod.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_repository_follows_the_rules() -> None:
    """El repositorio cumple el límite de líneas y el formato de docstrings."""
    assert check_standards.run(REPO_ROOT) == []


def test_flags_files_over_the_line_limit(tmp_path: Path) -> None:
    """Detecta un archivo con más de 250 líneas."""
    path = tmp_path / "largo.md"
    path.write_text("x\n" * (check_standards.MAX_LINES + 1), encoding="utf-8")
    assert check_standards.check_line_limit(path, tmp_path)
    path.write_text("x\n" * check_standards.MAX_LINES, encoding="utf-8")
    assert check_standards.check_line_limit(path, tmp_path) == []


@pytest.mark.parametrize(("source", "expected"), [
    ("def f():\n    pass\n", "falta la docstring"),
    ('def f(a):\n    """Hace algo."""\n', "falta el parámetro 'a' en Args"),
    ('def f():\n    """Hace algo."""\n    return 1\n', "falta la sección Returns"),
    ('def f():\n    """Hace algo."""\n    yield 1\n', "falta la sección Yields"),
    ('def f():\n    """Hace algo."""\n    raise ValueError\n', "falta la sección Raises"),
    ('def f() -> Iterator[int]:\n    """Hace algo."""\n    ...\n', "falta la sección Yields"),
])
def test_flags_incomplete_docstrings(tmp_path: Path, source: str, expected: str) -> None:
    """Detecta cada sección obligatoria ausente."""
    problems = check_standards.check_docstrings(_module(tmp_path, source), tmp_path, full=True)
    assert any(expected in p for p in problems)


def test_accepts_a_complete_docstring(tmp_path: Path) -> None:
    """Una docstring con todas las secciones no genera violaciones."""
    source = '''
def f(a: int, *args: int) -> int:
    """Suma valores.

    Args:
        a (int): Primer valor.
        *args (int): Valores adicionales.

    Returns:
        int: La suma.

    Raises:
        ValueError: Si ``a`` es negativo.
    """
    if a < 0:
        raise ValueError
    return a + sum(args)
'''
    assert check_standards.check_docstrings(_module(tmp_path, source), tmp_path, full=True) == []


def test_brief_mode_only_requires_a_description(tmp_path: Path) -> None:
    """En los tests basta la descripción breve."""
    source = 'def f(a):\n    """Hace algo."""\n    return a\n'
    assert check_standards.check_docstrings(_module(tmp_path, source), tmp_path, full=False) == []
