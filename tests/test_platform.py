from __future__ import annotations

from pathlib import Path

import pytest

from ffpfsc_converter.infrastructure import system
from ffpfsc_converter.infrastructure.mkpfs_adapter.process import kill_tree_command, popen_options
from ffpfsc_converter.infrastructure.system import desktop_dir, file_manager_command


@pytest.mark.parametrize(("platform", "program"), [
    ("win32", "explorer"),
    ("darwin", "open"),
    ("linux", "xdg-open"),
])
def test_file_manager_command_per_platform(platform: str, program: str) -> None:
    """Usa el gestor de archivos propio de cada sistema."""
    assert file_manager_command(Path("/salida"), platform) == [program, str(Path("/salida"))]


def test_popen_options_isolate_the_process_group() -> None:
    """Aísla a MkPFS en su grupo: sesión propia en POSIX y grupo sin consola en Windows."""
    assert popen_options(is_windows=False) == {"start_new_session": True}
    flags = popen_options(is_windows=True)["creationflags"]
    assert flags & 0x00000200  # CREATE_NEW_PROCESS_GROUP
    assert flags & 0x08000000  # CREATE_NO_WINDOW


def test_kill_tree_command_includes_children() -> None:
    """En Windows termina el árbol completo de procesos a la fuerza."""
    assert kill_tree_command(1234) == ["taskkill", "/PID", "1234", "/T", "/F"]


def test_desktop_dir_prefers_spanish_then_english(tmp_path: Path) -> None:
    """Encuentra Escritorio o Desktop y, si no hay ninguno, usa la carpeta personal."""
    assert desktop_dir(tmp_path) == tmp_path
    (tmp_path / "OneDrive" / "Desktop").mkdir(parents=True)
    assert desktop_dir(tmp_path) == tmp_path / "OneDrive" / "Desktop"
    (tmp_path / "Desktop").mkdir()
    assert desktop_dir(tmp_path) == tmp_path / "Desktop"
    (tmp_path / "Escritorio").mkdir()
    assert desktop_dir(tmp_path) == tmp_path / "Escritorio"


def test_windows_only_helpers_do_nothing_elsewhere() -> None:
    """La identidad de la app y la escala de Windows no hacen nada en Linux."""
    assert system.set_windows_app_id("x.y", platform="linux") is False
    assert system.enable_dpi_awareness(platform="linux") is False
