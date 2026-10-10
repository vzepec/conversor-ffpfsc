"""Diálogos y mensajes de la aplicación.

Centraliza todo uso de ``filedialog`` y ``messagebox`` para que la ventana
principal no mezcle textos de diálogo con su lógica.
"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from ffpfsc_converter.config import APP_TITLE, FREE_SPACE_MARGIN
from ffpfsc_converter.infrastructure.system import desktop_dir
from ffpfsc_converter.services.preflight import SpaceCheck
from ffpfsc_converter.ui.presenters import format_size

_IMAGE_FILETYPES = [("Imágenes de juego", "*.exfat *.ffpkg"), ("Todos", "*")]


def _initial_dir() -> str:
    """Elige la carpeta inicial de los selectores de archivos.

    Returns:
        str: Carpeta Escritorio del usuario o, si no existe, su carpeta personal.
    """
    return str(desktop_dir())


def ask_game_folder() -> Path | None:
    """Pide al usuario la carpeta de un juego.

    Returns:
        Path | None: Carpeta elegida, o ``None`` si canceló.
    """
    folder = filedialog.askdirectory(title="Selecciona la carpeta del juego",
                                     initialdir=_initial_dir())
    return Path(folder) if folder else None


def ask_game_image() -> Path | None:
    """Pide al usuario una imagen ``.exfat``/``.ffpkg``.

    Returns:
        Path | None: Archivo elegido, o ``None`` si canceló.
    """
    file = filedialog.askopenfilename(title="Selecciona la imagen del juego",
                                      initialdir=_initial_dir(), filetypes=_IMAGE_FILETYPES)
    return Path(file) if file else None


def ask_output_dir() -> Path | None:
    """Pide al usuario la carpeta donde guardar los ``.ffpfsc``.

    Returns:
        Path | None: Carpeta elegida, o ``None`` si canceló.
    """
    folder = filedialog.askdirectory(title="Carpeta donde guardar los .ffpfsc")
    return Path(folder) if folder else None


def show_info(message: str) -> None:
    """Muestra un mensaje informativo.

    Args:
        message (str): Texto a mostrar.
    """
    messagebox.showinfo(APP_TITLE, message)


def show_error(message: str) -> None:
    """Muestra un mensaje de error.

    Args:
        message (str): Texto a mostrar.
    """
    messagebox.showerror(APP_TITLE, message)


def confirm_overwrite(output: Path) -> bool:
    """Pregunta si se puede sobrescribir un archivo existente.

    Args:
        output (Path): Archivo que ya existe.

    Returns:
        bool: ``True`` si el usuario acepta sobrescribirlo.
    """
    return messagebox.askyesno(APP_TITLE, f"Ya existe:\n{output}\n\n¿Sobrescribir?")


def confirm_low_space(space: SpaceCheck) -> bool:
    """Advierte que el espacio libre probablemente no alcanza.

    Args:
        space (SpaceCheck): Espacio libre y necesario en destino.

    Returns:
        bool: ``True`` si el usuario decide continuar igualmente.
    """
    margin = (FREE_SPACE_MARGIN - 1) * 100
    return messagebox.askyesno(
        APP_TITLE,
        f"Espacio libre en destino: {format_size(space.free)}\n"
        f"Peso final estimado (+{margin:.0f}% margen): {format_size(space.needed)}\n\n"
        "Probablemente NO alcanza. ¿Continuar igual?")


def confirm_quit_while_running() -> bool:
    """Pregunta si se cancela la conversión en curso para salir.

    Returns:
        bool: ``True`` si el usuario acepta cancelar y salir.
    """
    return messagebox.askyesno(APP_TITLE, "Hay una conversión en curso. ¿Cancelarla y salir?")
