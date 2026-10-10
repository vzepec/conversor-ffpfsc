from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest

from ffpfsc_converter.domain.remote_events import FtpReady, PairingCodeRequired, RemoteError
from ffpfsc_converter.infrastructure import settings_store
from ffpfsc_converter.infrastructure.ava1.handshake import Ava1Refused, Established
from ffpfsc_converter.infrastructure.ava1.trust import TrustStore
from ffpfsc_converter.services.ftp_launcher import FtpLauncher

SERVER_KEY = b"\x07" * 32


class FakeSession:
    """Doble de Ava1Session que registra las llamadas."""

    instances: ClassVar[list[FakeSession]] = []

    def __init__(self, host: str, port: int, timeout: float, *, needs_code: bool = True,
                 refuse: Ava1Refused | None = None, reply: dict[str, Any] | None = None) -> None:
        """Guarda la configuración del doble."""
        self.needs_code, self.refuse = needs_code, refuse
        self.reply = reply or {"ok": True, "port": 2122}
        self.calls: list[tuple[int, dict[str, Any]]] = []
        self.paired_with: str | None = None
        self.closed = False
        FakeSession.instances.append(self)

    def handshake(self, identity: object, name: str, expected: bytes | None) -> Established:
        """Simula el handshake o un rechazo."""
        if self.refuse:
            raise self.refuse
        return Established(b"h" * 64, SERVER_KEY, "PS5 de prueba", self.needs_code, 3)

    def pair(self, code: str) -> None:
        """Registra el código usado."""
        self.paired_with = code

    def call_text(self, method: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Registra la llamada y devuelve la respuesta configurada."""
        self.calls.append((method, payload))
        return self.reply

    def close(self) -> None:
        """Marca la sesión como cerrada."""
        self.closed = True


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirige los ajustes a una carpeta temporal."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("APPDATA", raising=False)
    FakeSession.instances.clear()


def _launcher(events: list[object], tmp_path: Path, port_open: bool,
              code: str | None = "123456", **fake: Any) -> FtpLauncher:
    """Crea un lanzador simulado que responde ``code`` cuando se le pide, como la interfaz."""
    def emit(event: object) -> None:
        """Registra el evento y responde la solicitud de código."""
        events.append(event)
        if isinstance(event, PairingCodeRequired):
            launcher.provide_code(code)

    launcher = FtpLauncher(emit, TrustStore(tmp_path / "trust"),
                           session_factory=lambda h, p, t: FakeSession(h, p, t, **fake),
                           probe=lambda _h, _p: port_open)
    return launcher


def test_open_ftp_is_used_directly(tmp_path: Path) -> None:
    """Si el FTP ya responde, no se toca el helper."""
    events: list[object] = []
    _launcher(events, tmp_path, port_open=True).connect("10.0.0.5", 2122).join(5)
    assert events == [FtpReady(events[0].target, started=False)]
    assert not FakeSession.instances


def test_first_time_pairs_and_starts_readonly_ftp(tmp_path: Path) -> None:
    """La primera vez pide el código, empareja y arranca el FTP de solo lectura."""
    events: list[object] = []
    _launcher(events, tmp_path, port_open=False).connect("10.0.0.5", 2122).join(5)
    session = FakeSession.instances[0]
    assert isinstance(events[0], PairingCodeRequired)
    assert session.paired_with == "123456" and session.closed
    method, request = session.calls[0]
    assert method == 119 and request["readonly"] is True and request["port"] == 2122
    ready = events[-1]
    assert isinstance(ready, FtpReady) and ready.started
    assert (ready.target.user, ready.target.password) == (request["user"], request["pass"])
    assert TrustStore(tmp_path / "trust").known_key("10.0.0.5") == SERVER_KEY
    saved = settings_store.load_settings()["ftp_credentials"]["10.0.0.5"]
    assert saved == [request["user"], request["pass"]]


def test_cancelled_pairing(tmp_path: Path) -> None:
    """Sin código no se empareja ni se inicia el FTP."""
    events: list[object] = []
    _launcher(events, tmp_path, port_open=False, code=None).connect("10.0.0.5", 2122).join(5)
    assert isinstance(events[-1], RemoteError) and "cancelado" in events[-1].message
    assert FakeSession.instances[0].calls == []


def test_pairing_window_closed_explains_what_to_do(tmp_path: Path) -> None:
    """El error 2 indica recargar el payload y conectar en 5 minutos."""
    events: list[object] = []
    refusal = Ava1Refused(2, "this device is not paired and pairing is closed")
    _launcher(events, tmp_path, port_open=False, refuse=refusal).connect("h", 2122).join(5)
    assert isinstance(events[-1], RemoteError)
    assert "Vuelve a cargar el payload" in events[-1].message


def test_restart_stops_before_starting(tmp_path: Path) -> None:
    """Reiniciar envía ftp.start con puerto 0 antes del nuevo inicio."""
    events: list[object] = []
    launcher = _launcher(events, tmp_path, port_open=True, needs_code=False)
    launcher.connect("10.0.0.5", 2122, restart=True).join(5)
    calls = FakeSession.instances[0].calls
    assert calls[0] == (119, {"port": 0}) and calls[1][1]["port"] == 2122


def test_ftp_start_failure_is_reported(tmp_path: Path) -> None:
    """Una respuesta ok=false se informa con su causa."""
    events: list[object] = []
    reply = {"ok": False, "error": "bind_failed"}
    _launcher(events, tmp_path, port_open=False, needs_code=False, reply=reply) \
        .connect("h", 2122).join(5)
    assert isinstance(events[-1], RemoteError) and "bind_failed" in events[-1].message
