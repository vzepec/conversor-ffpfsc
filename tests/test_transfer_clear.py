from __future__ import annotations

import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import pytest

from ffpfsc_converter.domain.remote import DownloadJob, DownloadResult, RemoteEntry
from ffpfsc_converter.ui.explorer.retry_actions import RetryActions
from ffpfsc_converter.ui.explorer.transfer_header import TransferActions
from ffpfsc_converter.ui.explorer.transfer_panel import TransferPanel


@pytest.fixture
def root() -> tk.Tk:
    """Ventana oculta para crear widgets (se omite si no hay pantalla)."""
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("sin pantalla")
    window.withdraw()
    yield window
    window.destroy()


def test_clear_removes_only_finished_rows(root: tk.Tk, tmp_path: Path) -> None:
    """«Limpiar» quita lo terminado, fallido o cancelado y deja lo que sigue en curso."""
    from ffpfsc_converter.ui.theme import ThemeManager

    noop = lambda: None  # noqa: E731 - acciones sin efecto para el panel de prueba
    panel = TransferPanel(root, ThemeManager(root), TransferActions(noop, noop, noop, noop,
                                                                    noop))
    for row_id in ("ok", "bad", "run", "queued"):
        panel.add_row(row_id, row_id, "download")
    panel.set_state("ok", "ok", "✓ Listo")
    panel.set_state("bad", "bad", "Falló")
    panel.set_state("run", "run", "Descargando")
    assert sorted(panel.remove_finished()) == ["bad", "ok"]
    assert panel.row("run") and panel.row("queued") and panel.row("ok") is None
    assert panel.remove_finished() == []


def test_cleared_failures_are_not_retried(tmp_path: Path) -> None:
    """Lo que se quitó del panel ya no se reintenta con «Reintentar fallidas»."""
    enabled: list[bool] = []
    view = SimpleNamespace(transfers=SimpleNamespace(set_retry_enabled=enabled.append))
    retry = RetryActions(SimpleNamespace(view=view))  # type: ignore[arg-type]
    job = DownloadJob(RemoteEntry("a", "/data/a", False), tmp_path)
    retry.download_finished(job, DownloadResult(False, False, 0.0))
    retry.register_upload("up", tmp_path / "x", "/data")
    retry.upload_finished("up", succeeded=False)
    assert enabled[-1] is True
    retry.forget([job.id, "up"])
    assert enabled[-1] is False
