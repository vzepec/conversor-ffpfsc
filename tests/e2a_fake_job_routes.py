"""Rutas de conversión del exfat2ampr falso: start, state, pause, resume, cancel, retry…

Traducen parámetros HTTP a operaciones de :class:`e2a_fake_jobs.JobBoard` con
los mismos códigos de error que el motor real.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

from e2a_fake_data import FakeConsoleData, FakeReply, FakeRequest, error_reply, output_path
from e2a_fake_jobs import FakeJob, JobBoard

_TRUE = frozenset({"1", "t", "o"})
_OK = {"ok": True}

Route = Callable[[FakeRequest], FakeReply]


def _flag(params: Mapping[str, str], key: str, default: bool) -> bool:
    """Lee un flag ``"1"``/``"0"`` como el motor real (``t`` y ``o`` también son verdadero).

    Returns:
        bool: Valor del flag, o ``default`` si no vino.
    """
    value = params.get(key)
    return default if value is None else value[:1].lower() in _TRUE


class JobRoutes:
    """Responde las rutas que crean y controlan conversiones."""

    def __init__(self, console: FakeConsoleData, jobs: JobBoard) -> None:
        """Enlaza las rutas con los datos de la consola y los trabajos.

        Args:
            console (FakeConsoleData): Juegos y unidades.
            jobs (JobBoard): Conversión actual, cola y último resultado.
        """
        self.console = console
        self.jobs = jobs

    def routes(self) -> dict[str, Route]:
        """Asocia cada ruta con su manejador.

        Returns:
            dict[str, Route]: Ruta → función que la responde.
        """
        return {
            "/api/start": self._start, "/api/state": self._state, "/api/pause": self._pause,
            "/api/resume": self._resume, "/api/cancel": self._cancel, "/api/retry": self._retry,
            "/api/dismiss": self._dismiss, "/api/resumable": self._resumable,
        }

    def _start(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/start``: valida, crea el trabajo y lo pone en marcha o en cola.

        Returns:
            FakeReply: ``{"ok": true, "position": N}`` o el error del motor real.
        """
        params = request.params
        path, name = params.get("path", ""), params.get("name", "")
        game = self.console.games.get(path)
        if not path.startswith("/") or ".." in path or game is None:
            return error_reply(400, "bad path", "bad_path")
        dest = self.console.destination(params.get("dest", ""))
        if dest is None or not dest.writable:
            return error_reply(400, "destination unavailable", "dest_unavailable")
        if "/" in name or ".." in name:
            return error_reply(400, "bad name", "bad_name")
        job = FakeJob(game, output_path(dest.base, name or game.title_id),
                      level=int(params.get("level", "9")), remove=_flag(params, "remove", False))
        position = self.jobs.submit(job)
        if position is None:
            return error_reply(409, "queue full", "queue_full")
        return FakeReply(200, {"ok": True, "position": position})

    def _state(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/state``.

        Returns:
            FakeReply: Estado de la conversión o el último resultado.
        """
        return FakeReply(200, self.jobs.poll())

    def _pause(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/pause``.

        Returns:
            FakeReply: ``ok``.
        """
        self.jobs.pause()
        return FakeReply(200, _OK)

    def _resume(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/resume``.

        Returns:
            FakeReply: ``ok`` o 400 ``cannot resume``.
        """
        if self.jobs.resume(request.params.get("dest", "")):
            return FakeReply(200, _OK)
        return error_reply(400, "cannot resume")

    def _cancel(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/cancel`` (borra la salida a medio crear).

        Returns:
            FakeReply: ``ok``.
        """
        self.jobs.finish("cancelled", "user_cancel")
        return FakeReply(200, _OK)

    def _retry(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/retry``.

        Returns:
            FakeReply: ``ok`` o 409 ``nothing_to_retry``.
        """
        if self.jobs.retry():
            return FakeReply(200, _OK)
        return error_reply(409, "nothing to retry", "nothing_to_retry")

    def _dismiss(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/dismiss``.

        Returns:
            FakeReply: ``ok`` o 409 ``busy``.
        """
        if self.jobs.dismiss():
            return FakeReply(200, _OK)
        return error_reply(409, "busy", "busy")

    def _resumable(self, request: FakeRequest) -> FakeReply:
        """Responde ``/api/resumable``.

        Returns:
            FakeReply: Conversiones que se pueden reanudar.
        """
        return FakeReply(200, self.jobs.resumable())
