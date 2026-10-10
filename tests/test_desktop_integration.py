from __future__ import annotations

from pathlib import Path

from ffpfsc_converter.domain.events import QueueFinished
from ffpfsc_converter.domain.pipeline import PipelineResult
from ffpfsc_converter.domain.pipeline_events import PipelineFinished, UploadFinished
from ffpfsc_converter.domain.remote_events import DownloadQueueFinished
from ffpfsc_converter.infrastructure.notify import notify_command, send_notification
from ffpfsc_converter.infrastructure.power import SleepInhibitor, inhibit_command
from ffpfsc_converter.ui.notifications import Notification, Notifier, notification_for


def test_inhibit_command_blocks_sleep_while_running() -> None:
    """En Linux bloquea suspensión e inactividad mientras corre «sleep infinity»."""
    command = inhibit_command("Convirtiendo")
    assert command[0] == "systemd-inhibit" and "--what=sleep:idle" in command
    assert command[-2:] == ["sleep", "infinity"] and "--why=Convirtiendo" in command


def test_inhibitor_without_support_does_nothing() -> None:
    """Sin herramienta de bloqueo (o en un sistema no soportado) no falla."""
    linux = SleepInhibitor(platform="linux", which=lambda _name: None)
    assert linux.acquire("x") is False and not linux.active
    linux.release()
    assert SleepInhibitor(platform="darwin").acquire("x") is False


def test_notify_command_per_platform() -> None:
    """Usa notify-send en Linux y PowerShell (texto en variables de entorno) en Windows."""
    linux = notify_command("linux", "Título", "Texto", Path("/i.png"))
    assert linux == ["notify-send", "--app-name=Conversor FFPFSC (PS5)", "--icon=/i.png",
                     "Título", "Texto"]
    windows = notify_command("win32", "Título", "Texto", None)
    assert windows is not None and windows[0] == "powershell"
    assert "Título" not in " ".join(windows) and "$env:FFPFSC_TITLE" in windows[-1]
    assert notify_command("darwin", "a", "b", None) is None


def test_send_notification_needs_the_tool() -> None:
    """Si falta la herramienta, no envía nada y no falla."""
    assert send_notification("a", "b", None, platform="linux", which=lambda _n: None) is False


def test_notification_for_events() -> None:
    """Avisa al terminar bien o mal, pero no si el usuario canceló."""
    assert notification_for(QueueFinished(cancelled=False)).title == "Conversión terminada"
    assert notification_for(QueueFinished(cancelled=True)) is None
    assert notification_for(DownloadQueueFinished(cancelled=True)) is None
    ok = notification_for(UploadFinished("id", True, "/data/homebrew/a.ffpfsc"))
    assert ok == Notification("Subido a la PS5", "/data/homebrew/a.ffpfsc")
    failed = notification_for(PipelineFinished(PipelineResult(False, False, "\nSin red.\nMás")))
    assert failed == Notification("Comprimir y reemplazar no terminó", "Sin red.")
    assert notification_for(PipelineFinished(PipelineResult(False, True, "x"))) is None
    assert notification_for(object()) is None


class _Root:
    """Ventana falsa: indica si tiene el foco."""

    def __init__(self, focused: bool) -> None:
        """Guarda si la ventana tiene el foco."""
        self.focused = focused

    def focus_displayof(self) -> object | None:
        """Devuelve un widget si la ventana tiene el foco."""
        return self if self.focused else None


def test_notifier_only_when_window_is_not_focused() -> None:
    """Solo avisa si la ventana no tiene el foco."""
    sent: list[str] = []
    event = QueueFinished(cancelled=False)
    Notifier(_Root(True), lambda t, b, i: sent.append(t)).handle(event)  # type: ignore[arg-type]
    assert sent == []
    Notifier(_Root(False), lambda t, b, i: sent.append(t)).handle(event)  # type: ignore[arg-type]
    assert sent == ["Conversión terminada"]
