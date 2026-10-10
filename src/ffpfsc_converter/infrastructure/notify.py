"""Notificaciones del escritorio al terminar tareas largas (Linux y Windows).

- Linux: ``notify-send`` (libnotify), con el icono de la app.
- Windows: notificación nativa con PowerShell; el título y el texto viajan en
  variables de entorno, nunca dentro del código del script.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from ffpfsc_converter.config import APP_TITLE

_CREATE_NO_WINDOW = 0x08000000
_POWERSHELL_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
_TOAST_SCRIPT = (
    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
    "ContentType = WindowsRuntime] > $null; "
    "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
    "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
    "$x = $t.GetElementsByTagName('text'); "
    "$x.Item(0).AppendChild($t.CreateTextNode($env:FFPFSC_TITLE)) > $null; "
    "$x.Item(1).AppendChild($t.CreateTextNode($env:FFPFSC_BODY)) > $null; "
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
    f"'{_POWERSHELL_APP_ID}').Show([Windows.UI.Notifications.ToastNotification]::new($t))"
)


def notify_command(platform: str, title: str, body: str, icon: Path | None) -> list[str] | None:
    """Arma el comando que muestra una notificación.

    Args:
        platform (str): Valor de ``sys.platform``.
        title (str): Título.
        body (str): Texto.
        icon (Path | None): Icono (solo Linux).

    Returns:
        list[str] | None: Argumentos para ``subprocess.Popen``, o ``None`` si el
        sistema no está soportado.
    """
    if platform == "win32":
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", _TOAST_SCRIPT]
    if platform.startswith("linux"):
        icon_arg = [f"--icon={icon}"] if icon else []
        return ["notify-send", f"--app-name={APP_TITLE}", *icon_arg, title, body]
    return None


def send_notification(title: str, body: str, icon: Path | None, platform: str = sys.platform,
                      which: Callable[[str], str | None] = shutil.which) -> bool:
    """Muestra una notificación sin esperar a que se cierre (*best effort*).

    Args:
        title (str): Título.
        body (str): Texto.
        icon (Path | None): Icono (solo Linux).
        platform (str): Valor de ``sys.platform``.
        which (Callable[[str], str | None]): Busca programas (los tests usan un doble).

    Returns:
        bool: ``True`` si se lanzó la notificación.
    """
    command = notify_command(platform, title, body, icon)
    if command is None or not which(command[0]):
        return False
    env = {**os.environ, "FFPFSC_TITLE": title, "FFPFSC_BODY": body}
    flags = _CREATE_NO_WINDOW if platform == "win32" else 0
    try:
        subprocess.Popen(command, env=env, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True
