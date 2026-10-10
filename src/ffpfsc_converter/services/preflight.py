"""Comprobaciones previas a convertir."""
from __future__ import annotations

from dataclasses import dataclass

from ffpfsc_converter.config import FREE_SPACE_MARGIN
from ffpfsc_converter.domain.models import ConversionJob
from ffpfsc_converter.infrastructure.filesystem import free_space


@dataclass(frozen=True)
class SpaceCheck:
    """Comparación entre el espacio libre y el necesario en destino.

    Attributes:
        free (int): Bytes libres en el disco de destino.
        needed (int): Bytes estimados, con el margen de seguridad incluido.
    """

    free: int
    needed: int

    @property
    def is_enough(self) -> bool:
        """Indica si el espacio libre alcanza.

        Returns:
            bool: ``True`` si ``free >= needed``.
        """
        return self.free >= self.needed


def check_free_space(job: ConversionJob, level: int) -> SpaceCheck | None:
    """Compara el espacio libre en destino con el peso estimado más el margen.

    Args:
        job (ConversionJob): Trabajo ya analizado.
        level (int): Nivel de compresión elegido.

    Returns:
        SpaceCheck | None: Resultado de la comparación, o ``None`` si aún no se
        conoce el tamaño del juego.

    Raises:
        OSError: Si la carpeta de destino no existe o no se puede consultar.
    """
    if not job.size:
        return None
    estimate = job.estimate_for(level) or job.size
    return SpaceCheck(free_space(job.output.parent), int(estimate * FREE_SPACE_MARGIN))
