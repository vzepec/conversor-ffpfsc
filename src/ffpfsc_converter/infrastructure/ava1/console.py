"""Operaciones tipadas del helper: espacio libre y borrado recursivo (SPEC §7.1.1, §7.3).

El borrado usa ``job.run`` con la operación DELETE: corre en la consola, recorre
el árbol sin entrar en otros montajes y se niega a borrar raíces, carpetas de
primer nivel (``/data``, ``/mnt/usb0``), rutas no escribibles y puntos de montaje.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

from ffpfsc_converter.infrastructure.ava1.codec import Decoder, Encoder
from ffpfsc_converter.infrastructure.ava1.handshake import Ava1Refused
from ffpfsc_converter.infrastructure.ava1.session import Ava1Session

METHOD_JOB_STATUS = 17
METHOD_JOB_RUN = 20
METHOD_FS_FREESPACE = 44
JOB_OP_DELETE = 1
_STATE_RUNNING, _STATE_DONE = 0, 1
_EXT_CURRENT, _EXT_STATE, _EXT_RESULT, _EXT_CODE = 1, 2, 3, 4
_ERR_IO = 12
_POLL_SECONDS = 0.5


@dataclass(frozen=True)
class FreeSpace:
    """Espacio del disco de la PS5 que contiene una ruta.

    Attributes:
        usable (int): Bytes que una subida puede ocupar (libres menos el margen del helper).
        total (int): Capacidad del disco.
    """

    usable: int
    total: int


@dataclass(frozen=True)
class JobStatus:
    """Estado de una tarea ``job.run`` en la consola.

    Attributes:
        state (int): 0 en curso, 1 terminada bien, 2 fallida.
        files_done (int): Archivos procesados.
        files_total (int): Archivos totales (0 mientras se cuentan).
        current (str): Paso actual o causa del fallo.
        code (int): Código ``ERR_*`` si falló.
    """

    state: int
    files_done: int
    files_total: int
    current: str
    code: int


def free_space(session: Ava1Session, path: str) -> FreeSpace:
    """Consulta el espacio usable del disco que contiene una ruta de la PS5.

    Args:
        session (Ava1Session): Sesión emparejada.
        path (str): Ruta remota (se consulta su ancestro existente más cercano).

    Returns:
        FreeSpace: Espacio usable y capacidad.

    Raises:
        ConnectionError: Si la consola rechaza la consulta o se pierde la conexión.
    """
    d = Decoder(session.call(METHOD_FS_FREESPACE, Encoder().text(path).build()))
    usable, _free, total = d.u64(), d.u64(), d.u64()
    return FreeSpace(usable=usable, total=total)


def delete_tree(
    session: Ava1Session,
    path: str,
    on_progress: Callable[[JobStatus], None],
    poll_seconds: float = _POLL_SECONDS,
) -> None:
    """Borra un archivo o una carpeta completa en la PS5 y espera a que termine.

    Args:
        session (Ava1Session): Sesión emparejada.
        path (str): Ruta remota absoluta.
        on_progress (Callable[[JobStatus], None]): Recibe el estado en cada consulta.
        poll_seconds (float): Segundos entre consultas de estado.

    Raises:
        Ava1Refused: Si la consola se niega (ruta protegida, punto de montaje) o el borrado falla.
        ConnectionError: Si se pierde la conexión.
    """
    job_id = os.urandom(16)
    args = json.dumps({"path": path}).encode()
    body = Encoder().raw(job_id).u8(JOB_OP_DELETE).blob(args).build()
    status = _decode_status(session.call(METHOD_JOB_RUN, body))
    while status.state == _STATE_RUNNING:
        on_progress(status)
        time.sleep(poll_seconds)
        status = _decode_status(session.call(METHOD_JOB_STATUS, Encoder().raw(job_id).build()))
    on_progress(status)
    if status.state != _STATE_DONE:
        raise Ava1Refused(status.code or _ERR_IO, status.current or "fs_delete_failed")


def _decode_status(body: bytes) -> JobStatus:
    """Decodifica un mensaje ``Status``.

    Args:
        body (bytes): Cuerpo de la respuesta de ``job.run`` o ``job.status``.

    Returns:
        JobStatus: Campos relevantes del estado.
    """
    d = Decoder(body)
    d.raw(16)
    files_done, files_total = d.u32(), d.u32()
    for _ in range(3):  # bytes_received, bytes_durable, bytes_total
        d.u64()
    for _ in range(4):  # bottleneck, workers, lanes, sequential
        d.u8()
    ext = d.extensions()
    current = Decoder(ext[_EXT_CURRENT]).text() if _EXT_CURRENT in ext else ""
    if not current and _EXT_RESULT in ext:  # la causa de un fallo puede venir en `result`
        current = Decoder(ext[_EXT_RESULT]).blob().decode("utf-8", "replace")
    state = ext[_EXT_STATE][0] if _EXT_STATE in ext else _STATE_RUNNING
    code = int.from_bytes(ext[_EXT_CODE], "little") if _EXT_CODE in ext else 0
    return JobStatus(state, files_done, files_total, current, code)
