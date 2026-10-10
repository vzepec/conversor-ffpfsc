"""Tareas largas del helper con ``job.run``: borrado recursivo y CRC32 (SPEC §7.1.1).

Cada tarea corre en la consola en su propio hilo: se inicia, se consulta su
avance con ``job.status`` y se puede cancelar con ``job.cancel``.
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
METHOD_JOB_CANCEL = 18
METHOD_JOB_RUN = 20
JOB_OP_DELETE = 1
JOB_OP_CRC32 = 4
_STATE_RUNNING, _STATE_DONE = 0, 1
_EXT_CURRENT, _EXT_STATE, _EXT_RESULT, _EXT_CODE = 1, 2, 3, 4
_ERR_IO = 12
_POLL_SECONDS = 0.5


@dataclass(frozen=True)
class JobStatus:
    """Estado de una tarea ``job.run`` en la consola.

    Attributes:
        state (int): 0 en curso, 1 terminada bien, 2 fallida.
        files_done (int): Archivos procesados.
        files_total (int): Archivos totales (0 mientras se cuentan).
        current (str): Paso actual o causa del fallo.
        code (int): Código ``ERR_*`` si falló.
        bytes_done (int): Bytes procesados.
        bytes_total (int): Bytes totales (0 mientras se desconocen).
        result (str): Respuesta de la operación al terminar bien (JSON).
    """

    state: int
    files_done: int
    files_total: int
    current: str
    code: int
    bytes_done: int = 0
    bytes_total: int = 0
    result: str = ""


@dataclass(frozen=True)
class JobHandle:
    """Tarea iniciada en la consola.

    Attributes:
        job_id (bytes): Identificador (16 bytes) para consultarla o cancelarla.
        status (JobStatus): Estado devuelto al iniciarla.
    """

    job_id: bytes
    status: JobStatus


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
    job = start_job(session, JOB_OP_DELETE, path)
    wait_job(session, job, on_progress, lambda: False, poll_seconds)


def start_job(session: Ava1Session, op: int, path: str) -> JobHandle:
    """Inicia una operación ``job.run`` sobre una ruta (corre en la consola).

    Args:
        session (Ava1Session): Sesión emparejada.
        op (int): Operación (``JOB_OP_DELETE``, ``JOB_OP_CRC32``…).
        path (str): Ruta remota absoluta.

    Returns:
        JobHandle: Identificador y estado inicial de la tarea.

    Raises:
        Ava1Refused: Si la consola rechaza la operación.
        ConnectionError: Si se pierde la conexión.
    """
    job_id = os.urandom(16)
    args = json.dumps({"path": path}).encode()
    status = _decode_status(session.call(
        METHOD_JOB_RUN, Encoder().raw(job_id).u8(op).blob(args).build()))
    if status.state not in (_STATE_RUNNING, _STATE_DONE):
        raise Ava1Refused(status.code or _ERR_IO, status.current or "job_failed")
    return JobHandle(job_id, status)


def wait_job(session: Ava1Session, job: JobHandle, on_progress: Callable[[JobStatus], None],
             should_cancel: Callable[[], bool], poll_seconds: float = _POLL_SECONDS) -> JobStatus:
    """Espera a que termine una tarea, informando su avance; la cancela si se pide.

    Args:
        session (Ava1Session): Sesión emparejada.
        job (JobHandle): Tarea iniciada con :func:`start_job`.
        on_progress (Callable[[JobStatus], None]): Recibe el estado en cada consulta.
        should_cancel (Callable[[], bool]): Devuelve ``True`` para cancelar la tarea.
        poll_seconds (float): Segundos entre consultas de estado.

    Returns:
        JobStatus: Estado final (terminada bien), con la respuesta en ``result``.

    Raises:
        Ava1Refused: Si la tarea falla o se canceló.
        ConnectionError: Si se pierde la conexión.
    """
    status = job.status
    while status.state == _STATE_RUNNING:
        on_progress(status)
        if should_cancel():
            cancel_job(session, job.job_id)
        time.sleep(poll_seconds)
        status = job_status(session, job.job_id)
    on_progress(status)
    return check_done(status)


def cancel_job(session: Ava1Session, job_id: bytes) -> None:
    """Pide a la consola que detenga una tarea (vuelve enseguida).

    Args:
        session (Ava1Session): Sesión emparejada.
        job_id (bytes): Tarea a cancelar.

    Raises:
        ConnectionError: Si se pierde la conexión.
    """
    session.call(METHOD_JOB_CANCEL, Encoder().raw(job_id).build())


def is_running(status: JobStatus) -> bool:
    """Indica si una tarea sigue en curso.

    Args:
        status (JobStatus): Estado consultado.

    Returns:
        bool: ``True`` mientras no terminó (bien o mal).
    """
    return status.state == _STATE_RUNNING


def check_done(status: JobStatus) -> JobStatus:
    """Comprueba que una tarea terminada lo haya hecho bien.

    Args:
        status (JobStatus): Estado final.

    Returns:
        JobStatus: El mismo estado.

    Raises:
        Ava1Refused: Si la tarea falló o se canceló.
    """
    if status.state != _STATE_DONE:
        raise Ava1Refused(status.code or _ERR_IO, status.current or "job_failed")
    return status


def job_status(session: Ava1Session, job_id: bytes) -> JobStatus:
    """Consulta el estado de una tarea.

    Args:
        session (Ava1Session): Sesión emparejada.
        job_id (bytes): Tarea iniciada con :func:`start_job`.

    Returns:
        JobStatus: Avance actual.

    Raises:
        ConnectionError: Si se pierde la conexión.
    """
    return _decode_status(session.call(METHOD_JOB_STATUS, Encoder().raw(job_id).build()))


def crc32_result(status: JobStatus) -> int:
    """Extrae el CRC32 de la respuesta de una tarea ``JOB_OP_CRC32``.

    Args:
        status (JobStatus): Estado final de la tarea.

    Returns:
        int: CRC32 del archivo (el mismo que calcula ``zlib.crc32``).

    Raises:
        ValueError: Si la respuesta no trae un CRC32.
    """
    try:
        return int(json.loads(status.result)["crc32"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"respuesta de CRC32 inesperada: {status.result!r}") from exc


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
    received, durable, total = d.u64(), d.u64(), d.u64()
    for _ in range(4):  # bottleneck, workers, lanes, sequential
        d.u8()
    ext = d.extensions()
    result = (Decoder(ext[_EXT_RESULT]).blob().decode("utf-8", "replace")
              if _EXT_RESULT in ext else "")
    current = Decoder(ext[_EXT_CURRENT]).text() if _EXT_CURRENT in ext else ""
    state = ext[_EXT_STATE][0] if _EXT_STATE in ext else _STATE_RUNNING
    if not current and state != _STATE_DONE:  # la causa de un fallo puede venir en `result`
        current = result
    code = int.from_bytes(ext[_EXT_CODE], "little") if _EXT_CODE in ext else 0
    return JobStatus(state, files_done, files_total, current, code,
                     max(received, durable), total, result)
