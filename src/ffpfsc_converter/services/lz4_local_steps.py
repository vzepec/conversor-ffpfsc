"""Ejecución de las herramientas de ampr_emu como pasos de una conversión LZ4 en el PC.

Cada paso es un proceso (como MkPFS): se registra en el runner para poder
cancelarlo, su avance se publica como ``JobProgress`` (limitado) y el resto de su
salida va al registro técnico.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ffpfsc_converter.config import AMPR_RUNTIME_FILE, AMPR_TOOLS_DIR, PROGRESS_INTERVAL_SECONDS
from ffpfsc_converter.domain.events import EventSink, JobProgress, LogMessage
from ffpfsc_converter.domain.models import ConversionJob, ProgressUpdate
from ffpfsc_converter.infrastructure.ampr_tools import AmprTools
from ffpfsc_converter.infrastructure.third_party import installed
from ffpfsc_converter.services.process_handle import ProcessFactory, ProcessHandle
from ffpfsc_converter.services.skip_switch import SkipSwitch
from ffpfsc_converter.timing import PercentEta

#: Reconoce una línea de avance de una herramienta.
Parser = Callable[[str], ProgressUpdate | None]
#: Revisa cada línea; devuelve un motivo para detener la herramienta, o ``None``.
Guard = Callable[[str], str | None]
SKIPPED_TEXT = "Verificación omitida a pedido del usuario."


@dataclass(frozen=True)
class Lz4Components:
    """Herramientas de ampr_emu y biblioteca para el juego, ya instaladas.

    Attributes:
        tools (AmprTools): Scripts en Python.
        runtime (Path): ``libSceAmpr.sprx`` que va en ``fakelib/``.
    """

    tools: AmprTools
    runtime: Path


@dataclass(frozen=True)
class StepContext:
    """Lo que la conversión necesita del runner de la cola.

    Attributes:
        emit (EventSink): Destino de los eventos.
        process_factory (ProcessFactory): Lanza cada herramienta.
        cancel (threading.Event): Se activa al cancelar.
        set_process (Callable[[ProcessHandle | None], None]): Registra el proceso en curso
            para que el runner pueda terminarlo al cancelar.
        skip (SkipSwitch): Pedido de saltar el paso opcional en curso.
    """

    emit: EventSink
    process_factory: ProcessFactory
    cancel: threading.Event
    set_process: Callable[[ProcessHandle | None], None]
    skip: SkipSwitch = field(default_factory=SkipSwitch)


class StepFailedError(Exception):
    """Una herramienta terminó con error (el mensaje va al resultado)."""


def installed_components() -> Lz4Components | None:
    """Busca lo que dejó el instalador en ``third_party/``.

    Returns:
        Lz4Components | None: Componentes, o ``None`` si falta alguno.
    """
    tools, runtime = installed(AMPR_TOOLS_DIR), installed(AMPR_RUNTIME_FILE)
    return Lz4Components(AmprTools(tools), runtime) if tools and runtime else None


class ToolRunner:
    """Ejecuta una herramienta y reenvía su avance como el de un trabajo de la cola."""

    def __init__(self, ctx: StepContext, job: ConversionJob) -> None:
        """Prepara la ejecución para un trabajo.

        Args:
            ctx (StepContext): Eventos, procesos y cancelación.
            job (ConversionJob): Trabajo en curso.
        """
        self._ctx = ctx
        self._job = job
        self._stopped = ""

    def run(self, command: list[str], phase: str, parser: Parser | None = None,
            guard: Guard | None = None) -> list[str]:
        """Ejecuta una herramienta, publica su avance y devuelve su salida.

        Args:
            command (list[str]): Comando a ejecutar.
            phase (str): Fase que se muestra (``scan``, ``compress``, ``verify``).
            parser (Parser | None): Reconoce las líneas de avance; ``None`` = sin avance.
            guard (Guard | None): Detiene la herramienta si algo va mal (por ejemplo,
                si va a empaquetar más archivos de los previstos).

        Returns:
            list[str]: Líneas de salida (al menos una); vacía si se canceló.

        Raises:
            OSError: Si no se puede lanzar el proceso.
            StepFailedError: Si termina con un código distinto de 0 o la detuvo ``guard``.
        """
        if self._ctx.cancel.is_set():
            return []
        self._stopped = ""
        self._ctx.emit(JobProgress(self._job, ProgressUpdate(0, phase), None))
        process = self._ctx.process_factory(command)
        self._ctx.set_process(process)
        try:
            lines = self._follow(process, phase, parser, guard)
            code = process.wait()
        finally:
            self._ctx.set_process(None)
        if self._stopped:
            raise StepFailedError(self._stopped)
        if self._ctx.cancel.is_set():
            return []
        if code != 0:
            detail = next((line for line in reversed(lines) if line.strip()), "")
            raise StepFailedError(f"Falló el paso «{phase}» (código {code}): {detail}")
        return lines or [""]

    def run_optional(self, command: list[str], phase: str) -> bool:
        """Ejecuta un paso que el usuario puede saltar (la verificación).

        Si se salta, su proceso se termina y la conversión sigue como si hubiera
        terminado bien; no es una cancelación, así que no se borra nada.

        Args:
            command (list[str]): Comando a ejecutar.
            phase (str): Fase que se muestra.

        Returns:
            bool: ``True`` si terminó o se saltó; ``False`` si se canceló.

        Raises:
            OSError: Si no se puede lanzar el proceso.
            StepFailedError: Si falla sin que se haya pedido saltarlo.
        """
        self._ctx.skip.begin()
        try:
            done = bool(self.run(command, phase))
        except StepFailedError:
            if not self._ctx.skip.end():
                raise
            done = True
        skipped = self._ctx.skip.end()
        if skipped and not self._ctx.cancel.is_set():
            self._ctx.emit(LogMessage(SKIPPED_TEXT))
            return True
        return done

    def copy_progress(self) -> Callable[[int], bool]:
        """Crea el aviso de avance de la copia de archivos sueltos (fase ``write``).

        Returns:
            Callable[[int], bool]: Recibe los bytes copiados; ``False`` si hay que parar.
        """
        total, last = max(self._job.size, 1), [0.0]

        def report(copied: int) -> bool:
            """Publica el avance como máximo cada intervalo y responde si se sigue.

            Args:
                copied (int): Bytes copiados hasta ahora.

            Returns:
                bool: ``False`` si se pidió cancelar.
            """
            now = time.monotonic()
            if now - last[0] >= PROGRESS_INTERVAL_SECONDS:
                last[0] = now
                update = ProgressUpdate(min(copied * 100 // total, 100), "write")
                self._ctx.emit(JobProgress(self._job, update, None))
            return not self._ctx.cancel.is_set()

        return report

    def _follow(self, process: ProcessHandle, phase: str, parser: Parser | None,
                guard: Guard | None) -> list[str]:
        """Lee la salida, reenvía el avance (limitado) y el registro.

        Si ``guard`` da un motivo, termina el proceso y lo guarda en ``_stopped``.

        Args:
            process (ProcessHandle): Proceso lanzado.
            phase (str): Fase que se muestra.
            parser (Parser | None): Reconoce las líneas de avance.
            guard (Guard | None): Revisa cada línea.

        Returns:
            list[str]: Todas las líneas leídas.
        """
        lines: list[str] = []
        eta, last, in_json = PercentEta(), 0.0, False
        for line in process.lines():
            lines.append(line)
            if guard and not self._stopped and (reason := guard(line)):
                self._stopped = reason
                process.terminate()
            update = parser(line) if parser else None
            if update is None:
                in_json = in_json or line.rstrip() == "{"
                if not in_json:  # el resumen JSON final puede tener miles de líneas
                    self._ctx.emit(LogMessage(line))
                continue
            now = time.monotonic()
            if now - last >= PROGRESS_INTERVAL_SECONDS or update.percent >= 100:
                shown = ProgressUpdate(update.percent, phase, None)
                self._ctx.emit(JobProgress(self._job, shown, eta.update(phase, update.percent)))
                last = now
        return lines
