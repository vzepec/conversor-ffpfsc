"""Integración con el escritorio del sistema operativo (Linux, macOS y Windows)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

#: Nombres habituales de la carpeta Escritorio, en orden de preferencia.
_DESKTOP_CANDIDATES = (
    Path("Escritorio"),
    Path("Desktop"),
    Path("OneDrive") / "Escritorio",
    Path("OneDrive") / "Desktop",
)


def file_manager_command(path: Path, platform: str = sys.platform) -> list[str]:
    """Construye el comando que abre una carpeta en el gestor de archivos.

    Args:
        path (Path): Carpeta a abrir.
        platform (str): Valor de ``sys.platform`` del sistema destino.

    Returns:
        list[str]: ``explorer`` en Windows, ``open`` en macOS y ``xdg-open`` en Linux.
    """
    if platform == "win32":
        program = "explorer"
    elif platform == "darwin":
        program = "open"
    else:
        program = "xdg-open"
    return [program, str(path)]


def open_in_file_manager(path: Path) -> None:
    """Abre una carpeta con el gestor de archivos predeterminado.

    Args:
        path (Path): Carpeta a abrir.

    Raises:
        OSError: Si el programa del gestor de archivos no está disponible.
    """
    subprocess.Popen(
        file_manager_command(path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def desktop_dir(home: Path | None = None) -> Path:
    """Localiza la carpeta Escritorio del usuario.

    Args:
        home (Path | None): Carpeta personal; ``None`` usa ``Path.home()``.

    Returns:
        Path: Primera carpeta Escritorio existente, o la carpeta personal si no
        se encuentra ninguna.
    """
    home = home or Path.home()
    for candidate in _DESKTOP_CANDIDATES:
        if (home / candidate).is_dir():
            return home / candidate
    return home


def system_prefers_dark() -> bool | None:
    """Consulta si el sistema operativo usa el tema oscuro.

    Returns:
        bool | None: ``True`` si es oscuro, ``False`` si es claro, o ``None`` si no se
        puede saber (por ejemplo, un escritorio Linux sin esa preferencia).
    """
    try:
        import darkdetect  # import diferido: dependencia opcional para seguir el tema
    except ImportError:
        return None
    try:
        value = darkdetect.theme()
    except Exception:  # noqa: BLE001 - la consulta depende del escritorio; nunca debe romper la UI
        return None
    return None if value is None else value.lower() == "dark"


def enable_dpi_awareness(platform: str = sys.platform) -> bool:
    """Pide a Windows dibujar la ventana a resolución real (evita que se vea borrosa).

    Debe llamarse antes de crear la ventana. En otros sistemas no hace nada.

    Args:
        platform (str): Valor de ``sys.platform`` del sistema.

    Returns:
        bool: ``True`` si se activó el modo de alta resolución.
    """
    if platform != "win32":
        return False
    try:
        import ctypes  # import diferido: solo existe la API en Windows

        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False
    return True
