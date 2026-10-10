from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ffpfsc_converter.domain.events import (
    Event,
    JobFinished,
    JobProgress,
    JobStarted,
    LogMessage,
    QueueFinished,
)
from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions, JobState
from ffpfsc_converter.services.conversion import ConversionRunner

OPTIONS = ConversionOptions(3, 2, False)


class FakeProcess:
    """Doble de PackProcess: escribe la salida y emite líneas predefinidas."""

    def __init__(self, command: list[str], lines: list[str], return_code: int) -> None:
        """Guarda la salida esperada y las líneas que emitirá el proceso."""
        self.output = Path(command[-1])
        self._lines = lines
        self._rc = return_code
        self.terminated = False

    def lines(self) -> Iterator[str]:
        """Crea el archivo de salida y emite las líneas predefinidas."""
        self.output.write_bytes(b"x" * 10)
        yield from self._lines

    def wait(self) -> int:
        """Devuelve el código de salida configurado."""
        return self._rc

    def terminate(self) -> None:
        """Registra que se pidió terminar el proceso."""
        self.terminated = True


def _job(tmp_path: Path, name: str) -> ConversionJob:
    """Crea un trabajo de imagen con un archivo de origen de 100 bytes."""
    image = tmp_path / f"{name}.exfat"
    image.write_bytes(b"x" * 100)
    return ConversionJob(image, image, tmp_path / f"{name}.ffpfsc", size=100)


def _run(tmp_path: Path, jobs: list[ConversionJob], rc: int) -> list[Event]:
    """Ejecuta la cola con procesos falsos y devuelve los eventos publicados."""
    events: list[Event] = []
    runner = ConversionRunner(
        events.append,
        process_factory=lambda cmd: FakeProcess(cmd, ["[1/2] 50% compress", "hola"], rc),
    )
    runner.start(jobs, OPTIONS).join(timeout=5)
    assert not runner.is_running
    return events


def test_successful_queue(tmp_path: Path) -> None:
    """Convierte dos trabajos en orden y publica todos sus eventos."""
    jobs = [_job(tmp_path, "a"), _job(tmp_path, "b")]
    events = _run(tmp_path, jobs, rc=0)

    assert [type(e) for e in events] == [
        JobStarted, JobProgress, LogMessage, JobFinished,
        JobStarted, JobProgress, LogMessage, JobFinished,
        QueueFinished,
    ]
    finished = [e for e in events if isinstance(e, JobFinished)]
    assert all(e.result.succeeded and e.result.output_size == 10 for e in finished)
    assert all(j.state is JobState.SUCCEEDED for j in jobs)
    assert events[-1] == QueueFinished(cancelled=False)


def test_failure_removes_partial_output(tmp_path: Path) -> None:
    """Borra la salida parcial y marca el trabajo como fallido."""
    job = _job(tmp_path, "a")
    events = _run(tmp_path, [job], rc=1)
    result = next(e for e in events if isinstance(e, JobFinished)).result
    assert not result.succeeded and not result.cancelled
    assert result.message == "código 1"
    assert job.state is JobState.FAILED
    assert not job.output.exists()


def test_previous_cancel_does_not_affect_new_queue(tmp_path: Path) -> None:
    """Una cancelación previa no afecta a la siguiente cola."""
    events: list[Event] = []
    runner = ConversionRunner(events.append, process_factory=lambda cmd: FakeProcess(cmd, [], 0))
    runner.cancel()
    # start() limpia una cancelación anterior: debe convertir normalmente.
    runner.start([_job(tmp_path, "a")], OPTIONS).join(timeout=5)
    assert events[-1] == QueueFinished(cancelled=False)


def test_spawn_error_is_reported(tmp_path: Path) -> None:
    """Informa el error si el proceso no se puede lanzar."""
    def boom(_cmd: list[str]) -> FakeProcess:
        """Simula que el ejecutable no existe."""
        raise OSError("no python")

    events: list[Event] = []
    job = _job(tmp_path, "a")
    ConversionRunner(events.append, process_factory=boom).start([job], OPTIONS).join(timeout=5)
    result = next(e for e in events if isinstance(e, JobFinished)).result
    assert result.message == "no python"
    assert job.state is JobState.FAILED
