"""Diálogos y mensajes de la aplicación.

Centraliza todo uso de ``filedialog`` y ``messagebox`` para que la ventana
principal no mezcle textos de diálogo con su lógica.
"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from ffpfsc_converter.config import APP_TITLE, FREE_SPACE_MARGIN
from ffpfsc_converter.services.preflight import SpaceCheck
from ffpfsc_converter.ui.presenters import format_size

_IMAGE_FILETYPES = [("Imágenes de juego", "*.exfat *.ffpkg"), ("Todos", "*")]


def _initial_dir() -> str:
    """Elige la carpeta inicial de los selectores de archivos.

    Returns:
        str: ``~/Escritorio`` si existe; si no, la carpeta personal.
    """
    desktop = Path.home() / "Escritorio"
    return str(desktop if desktop.exists() else Path.home())


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


def ask_pairing_code(console_name: str) -> str | None:
    """Pide el código de emparejamiento que muestra la PS5.

    Args:
        console_name (str): Nombre de la consola, para el mensaje.

    Returns:
        str | None: Código escrito, o ``None`` si el usuario canceló.
    """
    return simpledialog.askstring(
        APP_TITLE,
        f"Emparejar con {console_name}\n\n"
        "La PS5 muestra una notificación con un código de 6 dígitos.\n"
        "Escríbelo aquí (tienes menos de un minuto):",
    )


def ask_download_dir() -> Path | None:
    """Pide la carpeta donde guardar las descargas de la PS5.

    Returns:
        Path | None: Carpeta elegida, o ``None`` si canceló.
    """
    folder = filedialog.askdirectory(title="Carpeta donde guardar las descargas de la PS5",
                                     initialdir=_initial_dir())
    return Path(folder) if folder else None


def confirm_resume_download(path: Path) -> bool:
    """Advierte que el destino ya existe y se completará o reemplazará.

    Args:
        path (Path): Archivo o carpeta local que ya existe.

    Returns:
        bool: ``True`` si el usuario acepta continuar.
    """
    return messagebox.askyesno(
        APP_TITLE,
        f"Ya existe:\n{path}\n\nSe completarán los archivos que falten o estén a medias, y se "
        "reemplazarán los que tengan otro tamaño. ¿Continuar?")


def confirm_quit_while_downloading() -> bool:
    """Pregunta si se cancelan las descargas en curso para salir.

    Returns:
        bool: ``True`` si el usuario acepta salir (las descargas se podrán reanudar).
    """
    return messagebox.askyesno(
        APP_TITLE, "Hay descargas en curso. ¿Salir igualmente? Podrás reanudarlas después.")


def confirm_remote_delete(summary: str) -> bool:
    """Pide confirmación antes de borrar en la PS5.

    Args:
        summary (str): Rutas que se borrarán, una por línea.

    Returns:
        bool: ``True`` si el usuario acepta borrar.
    """
    return messagebox.askyesno(
        APP_TITLE, f"Se BORRARÁ de la PS5 (incluido todo su contenido):\n\n{summary}\n\n"
        "Esta acción no se puede deshacer. ¿Continuar?", icon="warning", default="no")


def ask_upload_files() -> list[Path]:
    """Pide los archivos de este equipo que se subirán a la PS5.

    Returns:
        list[Path]: Archivos elegidos (vacía si canceló).
    """
    files = filedialog.askopenfilenames(title="Archivos a subir a la PS5",
                                        initialdir=_initial_dir())
    return [Path(f) for f in files]


def confirm_warning(message: str) -> bool:
    """Pide una confirmación con icono de advertencia (por defecto, "No").

    Args:
        message (str): Pregunta.

    Returns:
        bool: ``True`` si el usuario acepta.
    """
    return messagebox.askyesno(APP_TITLE, message, icon="warning", default="no")


def confirm(message: str) -> bool:
    """Pide una confirmación simple (Sí / No).

    Args:
        message (str): Pregunta.

    Returns:
        bool: ``True`` si el usuario acepta.
    """
    return messagebox.askyesno(APP_TITLE, message)
