from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ffpfsc_converter.domain.remote import StorageVolume
from ffpfsc_converter.domain.remote_events import StorageUpdated
from ffpfsc_converter.infrastructure.ava1.console import METHOD_FS_VOLUMES, list_volumes
from ffpfsc_converter.infrastructure.ava1.handshake import Established
from ffpfsc_converter.infrastructure.ava1.trust import TrustStore
from ffpfsc_converter.services.console_access import ConsoleAccess
from ffpfsc_converter.services.remote_storage import StorageMonitor
from ffpfsc_converter.ui.explorer import presenters

GB = 1024**3
INTERNAL = {"path": "/data", "mount_from": "/dev/ssd0.user", "total_bytes": 825 * GB,
            "free_bytes": 412 * GB, "source_image": ""}
USB = {"path": "/mnt/usb0", "mount_from": "/dev/da0s1", "total_bytes": 64 * GB,
       "free_bytes": 58 * GB, "source_image": ""}
IMAGE = {"path": "/mnt/ps5upload/juego", "mount_from": "/dev/lvd2", "total_bytes": 50 * GB,
         "free_bytes": 0, "source_image": "/data/homebrew/juego.exfat"}


class FakeSession:
    """Doble de Ava1Session que responde ``fs.volumes``."""

    def __init__(self, volumes: list[object], *, needs_code: bool = False) -> None:
        """Guarda la respuesta y si la consola conoce a la app."""
        self.volumes, self.needs_code = volumes, needs_code
        self.calls: list[tuple[int, dict[str, Any]]] = []
        self.closed = False

    def handshake(self, identity: object, name: str, expected: bytes | None) -> Established:
        """Simula el handshake."""
        return Established(b"h" * 64, b"\x07" * 32, "PS5", self.needs_code, 3)

    def call_text(self, method: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Registra la llamada y devuelve las unidades."""
        self.calls.append((method, payload))
        return {"volumes": self.volumes}

    def close(self) -> None:
        """Marca la sesión como cerrada."""
        self.closed = True


def _monitor(tmp_path: Path, session: FakeSession, events: list[object]) -> StorageMonitor:
    """Crea el servicio con una sesión simulada."""
    access = ConsoleAccess(TrustStore(tmp_path / "trust"), lambda _h, _p, _t: session)
    return StorageMonitor(events.append, access)


def test_list_volumes_skips_mounted_images_and_bad_entries() -> None:
    """Devuelve los discos reales y descarta imágenes montadas y entradas mal formadas."""
    session = FakeSession([INTERNAL, IMAGE, {"path": "/mnt/usb1"}, "basura", USB])
    volumes = list_volumes(session)  # type: ignore[arg-type]
    assert session.calls == [(METHOD_FS_VOLUMES, {})]
    assert volumes == (StorageVolume("/data", "/dev/ssd0.user", 825 * GB, 412 * GB),
                       StorageVolume("/mnt/usb0", "/dev/da0s1", 64 * GB, 58 * GB))


def test_monitor_publishes_volumes_and_closes_session(tmp_path: Path) -> None:
    """Publica las unidades de la consola y cierra la sesión."""
    events: list[object] = []
    session = FakeSession([INTERNAL, USB])
    thread = _monitor(tmp_path, session, events).refresh("10.0.0.5")
    assert thread is not None
    thread.join(5)
    assert len(events) == 1 and isinstance(events[0], StorageUpdated)
    assert [v.path for v in events[0].volumes] == ["/data", "/mnt/usb0"]
    assert session.closed


def test_monitor_reports_unpaired_app_without_asking_code(tmp_path: Path) -> None:
    """Si la app no está emparejada, informa el motivo y no pide código."""
    events: list[object] = []
    session = FakeSession([INTERNAL], needs_code=True)
    thread = _monitor(tmp_path, session, events).refresh("10.0.0.5")
    assert thread is not None
    thread.join(5)
    assert events == [StorageUpdated((), "la app no está emparejada con esta PS5")]
    assert not session.calls


def test_refresh_during_a_query_repeats_it_once(tmp_path: Path) -> None:
    """Las peticiones que llegan durante una consulta se juntan en una sola repetición."""
    events: list[object] = []
    release = threading.Event()
    session = FakeSession([USB])
    original = session.call_text

    def slow_call(method: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Espera a que el test termine de pedir más actualizaciones."""
        release.wait(5)
        return original(method, payload)

    session.call_text = slow_call  # type: ignore[method-assign]
    monitor = _monitor(tmp_path, session, events)
    thread = monitor.refresh("10.0.0.5")
    assert monitor.refresh("10.0.0.5") is None and monitor.refresh("10.0.0.5") is None
    release.set()
    assert thread is not None
    thread.join(5)
    assert len(events) == 2


def test_volume_names() -> None:
    """Nombra el interno, los USB y el ampliado (M.2 o USB) como los ve el usuario."""
    def volume(path: str, device: str = "/dev/da0") -> StorageVolume:
        """Crea una unidad de prueba."""
        return StorageVolume(path, device, GB, GB)

    assert presenters.volume_name(volume("/data", "/dev/ssd0")) == "Interno"
    assert presenters.volume_name(volume("/mnt/usb0")) == "USB 1"
    assert presenters.volume_name(volume("/mnt/usb1")) == "USB 2"
    assert presenters.volume_name(volume("/mnt/ext0", "/dev/nvme0")) == "M.2"
    assert presenters.volume_name(volume("/mnt/ext1")) == "USB ampliado 2"
