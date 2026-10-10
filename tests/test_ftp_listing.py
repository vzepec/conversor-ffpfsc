from __future__ import annotations

import pytest

from ffpfsc_converter.domain.remote import RemoteEntry
from ffpfsc_converter.infrastructure.ftp import (
    entries_from_mlsd,
    is_safe_name,
    join_remote,
    parse_list_line,
    sort_entries,
)


@pytest.mark.parametrize(("name", "safe"), [
    ("juego.ffpfsc", True),
    ("Mi Juego (v1.00)", True),
    (".", False),
    ("..", False),
    ("", False),
    ("../../etc", False),
    ("a/b", False),
    ("a\\b", False),
])
def test_is_safe_name(name: str, safe: bool) -> None:
    """Rechaza nombres que permitirían salir de la carpeta de destino."""
    assert is_safe_name(name) is safe


def test_join_remote_normalizes() -> None:
    """Une rutas POSIX sin dobles barras."""
    assert join_remote("/data/", "homebrew") == "/data/homebrew"
    assert join_remote("/", "data") == "/data"


def test_entries_from_mlsd_like_ps5upload() -> None:
    """Filtra '.', '..' (que ps5upload marca como dir) y nombres inseguros."""
    rows = [
        (".", {"type": "dir"}),
        ("..", {"type": "dir"}),
        ("homebrew", {"type": "dir", "size": "512", "modify": "20261009120000"}),
        ("juego.ffpfsc", {"type": "file", "size": "1234", "modify": "20261009120000"}),
        ("x", {"type": "cdir"}),
        ("../malo", {"type": "file", "size": "1"}),
    ]
    assert entries_from_mlsd("/data", rows) == [
        RemoteEntry("homebrew", "/data/homebrew", True, 0, "20261009120000"),
        RemoteEntry("juego.ffpfsc", "/data/juego.ffpfsc", False, 1234, "20261009120000"),
    ]


def test_parse_list_line() -> None:
    """Interpreta líneas estilo 'ls -l', incluidos nombres con espacios."""
    entry = parse_list_line("/data", "-rw-r--r-- 1 root wheel 2048 Oct 09 12:00 mi juego.exfat")
    assert entry == RemoteEntry("mi juego.exfat", "/data/mi juego.exfat", False, 2048)
    folder = parse_list_line("/", "drwxr-xr-x 1 root wheel 512 Oct 09 12:00 data")
    assert folder is not None and folder.is_dir
    assert parse_list_line("/", "total 12") is None
    assert parse_list_line("/", "drwxr-xr-x 1 root wheel 512 Oct 09 12:00 ..") is None


def test_sort_entries_dirs_first() -> None:
    """Ordena carpetas antes que archivos y sin distinguir mayúsculas."""
    entries = [
        RemoteEntry("b.bin", "/b.bin", False),
        RemoteEntry("Zeta", "/Zeta", True),
        RemoteEntry("A.bin", "/A.bin", False),
        RemoteEntry("alfa", "/alfa", True),
    ]
    assert [e.name for e in sort_entries(entries)] == ["alfa", "Zeta", "A.bin", "b.bin"]
