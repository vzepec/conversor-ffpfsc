"""Trabajos del exfat2ampr falso: cola, avance, pausa, cancelación y último resultado.

Imita una particularidad del motor real: tras terminar, ``/api/state`` sigue
devolviendo el último resultado (``done``/``error``/``cancelled``) hasta que
arranca otra conversión, así que justo después de ``/api/start`` puede verse aún
el resultado anterior (``stale_polls`` lo simula).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from e2a_fake_data import FakeConsoleData, FakeGame

FINISHED = frozenset({"done", "error", "cancelled"})


@dataclass
class FakeJob:
    """Conversión aceptada por el motor falso.

    Attributes:
        game (FakeGame): Juego de origen.
        dest (str): Carpeta de salida (``<dest>/<name>``).
        level (int): Nivel LZ4.
        remove (bool): Borrar el origen al terminar bien.
        state (str): ``pending``, ``running``, ``paused`` o un estado final.
        percent (int): Avance.
        code (str): Motivo del resultado o de la pausa.
        stale_left (int): Consultas de estado que aún verán el resultado anterior.
    """

    game: FakeGame
    dest: str
    level: int = 9
    remove: bool = False
    state: str = "pending"
    percent: int = 0
    code: str = ""
    stale_left: int = 0


def status_json(job: FakeJob | None, queue: list[FakeJob]) -> dict[str, object]:
    """Representa el estado como lo hace ``/api/state``.

    Returns:
        dict[str, object]: Objeto JSON con todos los campos del motor real.
    """
    state = "idle" if job is None else ("running" if job.state == "pending" else job.state)
    size = job.game.size if job else 0
    done = size * (job.percent if job else 0) // 100
    return {
        "version": "1.45", "state": state, "phase": "pack" if state == "running" else "",
        "message": "", "code": job.code if job else "", "reason": "", "waiting": False,
        "can_retry": state in ("error", "cancelled"), "resumable": state == "paused",
        "deleting": False, "percent": job.percent if job else 0, "bytes_total": size,
        "bytes_done": done, "speed_bps": 50 * 1024**2 if state == "running" else 0,
        "eta_seconds": 60 if state == "running" else -1,
        "title_id": job.game.title_id if job else "", "title": job.game.title if job else "",
        "dest": job.dest if job else "", "profile": "", "source_bytes": size,
        "packed_bytes": done // 2, "shared_bytes": 0, "started": 0, "finished": 0,
        "queue": [queued.game.title_id for queued in queue], "runtime": {},
        "storage_rev": 0, "game_running": "", "game_mode": False,
        "game_mode_enabled": False, "log": "",
    }


class JobBoard:
    """Conversión actual, cola y último resultado del motor falso (sin bloqueo propio)."""

    def __init__(self, console: FakeConsoleData, queue_capacity: int = 2) -> None:
        """Empieza sin conversiones y con el estado ``idle``.

        ``auto_step`` (puntos que avanza en cada consulta de estado) y ``stale_polls``
        (consultas que aún ven el resultado anterior tras ``start``) empiezan en 0.

        Args:
            console (FakeConsoleData): Juegos y carpetas que cambian al terminar.
            queue_capacity (int): Conversiones en espera antes de responder ``queue_full``.
        """
        self.console = console
        self.queue_capacity = queue_capacity
        self.current: FakeJob | None = None
        self.queue: list[FakeJob] = []
        self.result: FakeJob | None = None
        self.auto_step = 0
        self.stale_polls = 0

    def submit(self, job: FakeJob) -> int | None:
        """Acepta una conversión; empieza ya o queda en cola.

        Args:
            job (FakeJob): Conversión pedida.

        Returns:
            int | None: Lugar en la cola, o ``None`` si la cola está llena.
        """
        if self.current is None:
            job.stale_left = self.stale_polls
            self.current = job
            return 0
        if len(self.queue) >= self.queue_capacity:
            return None
        self.queue.append(job)
        return len(self.queue)

    def poll(self) -> dict[str, object]:
        """Responde ``/api/state`` y avanza ``auto_step`` puntos si hay una conversión.

        Returns:
            dict[str, object]: Estado actual (o el resultado anterior si aún no arrancó).
        """
        job = self.current
        if job is not None and job.stale_left > 0:
            job.stale_left -= 1
            return status_json(self.result, self.queue)
        if job is not None and job.state == "pending":
            job.state = "running"
        if job is not None and job.state == "running" and self.auto_step:
            self.advance(job.percent + self.auto_step)
        return status_json(self.current or self.result, self.queue)

    def advance(self, percent: int) -> None:
        """Lleva la conversión actual a un porcentaje (al 100 % termina en ``done``).

        Args:
            percent (int): Nuevo avance.
        """
        job = self.current
        if job is None:
            return
        job.state, job.stale_left, job.percent = "running", 0, min(percent, 100)
        if job.percent >= 100:
            self.finish("done")

    def finish(self, state: str, code: str = "") -> None:
        """Termina la conversión actual y deja su resultado visible.

        Args:
            state (str): ``done``, ``error``, ``cancelled`` o ``paused``.
            code (str): Motivo (``disk_full``, ``not_ampr``…).
        """
        job = self.current
        if job is None:
            return
        job.state, job.code, job.stale_left = state, code, 0
        if state == "paused":
            return
        self._apply_result(job)
        self.result, self.current = job, (self.queue.pop(0) if self.queue else None)

    def _apply_result(self, job: FakeJob) -> None:
        """Refleja en la consola falsa el resultado de una conversión.

        Args:
            job (FakeJob): Conversión que terminó.
        """
        if job.state == "done":
            job.percent = 100
            self.console.existing.add(job.dest)
            if job.remove:
                self.console.games.pop(job.game.path, None)
        elif job.state == "cancelled":
            self.console.existing.discard(job.dest)

    def pause(self) -> None:
        """Pausa la conversión actual dejando un punto de reanudación."""
        if self.current is not None and self.current.state in ("pending", "running"):
            self.finish("paused", "user_pause")

    def resume(self, dest: str) -> bool:
        """Reanuda la conversión en pausa cuya salida es ``dest``.

        Args:
            dest (str): Carpeta de salida.

        Returns:
            bool: ``False`` si no hay nada que reanudar ahí.
        """
        job = self.current
        if job is None or job.state != "paused" or job.dest != dest.rstrip("/"):
            return False
        job.state, job.code = "running", ""
        return True

    def retry(self) -> bool:
        """Repite la última conversión fallida o cancelada.

        Returns:
            bool: ``False`` si no hay nada que repetir o hay otra en curso.
        """
        last = self.result
        if self.current is not None or last is None or last.state not in ("error", "cancelled"):
            return False
        self.current = replace(last, state="running", percent=0, code="", stale_left=0)
        return True

    def dismiss(self) -> bool:
        """Descarta el último resultado (el estado vuelve a ``idle``).

        Returns:
            bool: ``False`` si hay una conversión en curso.
        """
        if self.current is not None and self.current.state != "paused":
            return False
        self.current = self.result = None
        return True

    def resumable(self) -> list[dict[str, object]]:
        """Responde ``/api/resumable``.

        Returns:
            list[dict[str, object]]: La conversión en pausa, si la hay.
        """
        job = self.current
        if job is None or job.state != "paused":
            return []
        return [{"dest": job.dest, "source": job.game.path, "name": job.game.title_id,
                 "stage": "pack", "source_available": True, "active": False,
                 "level": job.level}]
