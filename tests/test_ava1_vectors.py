from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from ffpfsc_converter.infrastructure.ava1 import keys
from ffpfsc_converter.infrastructure.ava1.codec import Decoder, Encoder
from ffpfsc_converter.infrastructure.ava1.frames import encode_header
from ffpfsc_converter.infrastructure.ava1.noise import NoiseInitiator

VECTORS = Path(__file__).parent / "vectors" / "ava1"


def _lines(name: str) -> list[list[str]]:
    """Lee un archivo de vectores sin comentarios ni líneas vacías."""
    text = (VECTORS / name).read_text()
    return [ln.split() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]


def _x(hexa: str) -> bytes:
    """Convierte hexadecimal en bytes."""
    return bytes.fromhex(hexa)


def test_frame_headers() -> None:
    """La cabecera con CRC32C coincide con los vectores oficiales."""
    for ty, flags, channel, body_len, expected in _lines("frame_header.txt"):
        header = encode_header(int(ty, 16), int(flags, 16), int(channel), int(body_len))
        assert header.hex() == expected


def test_control_and_lane_keys() -> None:
    """Las claves de carril coinciden con keys.txt."""
    for row in _lines("keys.txt"):
        if row[0] == "lane_key":
            out = keys.lane_key(_x(row[1]), int(row[2]), _x(row[3]), _x(row[4]))
            assert out.hex() == row[6]


def test_pair_commit() -> None:
    """El compromiso de emparejamiento coincide con pairing.txt."""
    for _, nonce, commit in _lines("pairing.txt"):
        assert keys.pair_commit(_x(nonce)).hex() == commit


@pytest.mark.parametrize("row", _lines("cpace.txt"), ids=lambda r: r[2])
def test_cpace_chain(row: list[str]) -> None:
    """Generador, valores públicos, K y ambos MAC coinciden con cpace.txt."""
    _, h, code, xa, xb, g, ya, yb, k, mac_c, mac_s = row
    assert keys.generator(_x(h), code).hex() == g
    assert keys.x25519(_x(xa), _x(g)).hex() == ya
    assert keys.x25519(_x(xb), _x(g)).hex() == yb
    key = keys.pake_key(_x(h), _x(xa), _x(yb), _x(ya), _x(yb))
    assert key.hex() == k
    assert keys.pake_mac(key, b"client", _x(h)).hex() == mac_c
    assert keys.pake_mac(key, b"server", _x(h)).hex() == mac_s


def test_noise_xx_initiator_matches_cacophony() -> None:
    """El handshake del iniciador reproduce el vector de cacophony."""
    v = json.loads((VECTORS / "noise_xx.json").read_text())
    noise = NoiseInitiator(
        X25519PrivateKey.from_private_bytes(_x(v["init_static"])),
        _x(v["init_prologue"]),
        ephemeral=X25519PrivateKey.from_private_bytes(_x(v["init_ephemeral"])),
    )
    m = v["messages"]
    assert noise.write_message_1(_x(m[0]["payload"])).hex() == m[0]["ciphertext"]
    assert noise.read_message_2(_x(m[1]["ciphertext"])).hex() == m[1]["payload"]
    assert noise.write_message_3(_x(m[2]["payload"])).hex() == m[2]["ciphertext"]
    assert noise.h.hex() == v["handshake_hash"]
    c2s, s2c = noise.split()
    # Los mensajes de transporte alternan: el 4.º va de la consola al cliente.
    assert ChaCha20Poly1305(s2c).decrypt(bytes(12), _x(m[3]["ciphertext"]), b"").hex() \
        == m[3]["payload"]
    assert ChaCha20Poly1305(c2s).encrypt(bytes(12), _x(m[4]["payload"]), b"").hex() \
        == m[4]["ciphertext"]


def test_codec_round_trips_canonical_messages() -> None:
    """Codifica igual que los vectores Ping, Error y RpcRequest."""
    canon = {row[0]: row[1] for row in _lines("messages.txt")}
    assert Encoder().u32(5).u64(0x0102030405060708).build().hex() == canon["Ping"]
    rpc = Encoder().u16(1).blob(b"\xaa\xbb").build()
    assert rpc.hex() == canon["RpcRequest"]
    d = Decoder(_x(canon["Error"]))
    assert (d.u16(), d.text(), d.extensions()) == (0x0102, "no", {})
    d = Decoder(_x(canon["PairResult"]))
    assert (d.u8(), d.raw(32), d.extensions()) == (1, b"\xcd" * 32, {})


def test_status_vector_decodes() -> None:
    """El estado de una tarea se lee igual que el vector oficial Status."""
    from ffpfsc_converter.infrastructure.ava1.console import _decode_status

    canon = {row[0]: row[1] for row in _lines("messages.txt")}
    status = _decode_status(_x(canon["Status"]))
    assert (status.state, status.code, status.current) == (2, 12, "cause")
    assert (status.files_done, status.files_total) == (1, 1)


def test_text_field_encoding() -> None:
    """Un campo str se codifica como u16 + UTF-8."""
    assert Encoder().text("/data").build().hex() == "05002f646174610000"
