"""Comprobaciones previas a convertir (espacio en disco, sobrescritura)."""
from __future__ import annotations

from dataclasses import dataclass

from ffpfsc_converter.config import FREE_SPACE_MARGIN
from ffpfsc_converter.domain.models import ConversionJob
from ffpfsc_converter.infrastructure.filesystem import free_space


@dataclass(frozen=True)
class SpaceCheck:
    free: int
    needed: int

    @property
    def is_enough(self) -> bool:
        return self.free >= self.needed


def check_free_space(job: ConversionJob, level: int) -> SpaceCheck | None:
    """Compara el espacio libre en destino con el peso estimado (+ margen).

    Devuelve ``None`` si aún no se conoce el tamaño del juego.
    """
    if not job.size:
        return None
    estimate = job.estimate_for(level) or job.size
    return SpaceCheck(free_space(job.output.parent), int(estimate * FREE_SPACE_MARGIN))
