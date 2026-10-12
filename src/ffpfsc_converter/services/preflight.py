"""Comprobaciones previas a convertir."""
from __future__ import annotations

from dataclasses import dataclass

from ffpfsc_converter.config import FREE_SPACE_MARGIN
from ffpfsc_converter.domain.models import ConversionJob, ConversionOptions, OutputFormat
from ffpfsc_converter.infrastructure.filesystem import free_space, same_device


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


def check_free_space(job: ConversionJob, options: ConversionOptions) -> SpaceCheck | None:
    """Compara el espacio libre en destino con el peso estimado más el margen.

    Args:
        job (ConversionJob): Trabajo ya analizado.
        options (ConversionOptions): Nivel de compresión y rendimiento elegidos.

    Returns:
        SpaceCheck | None: Resultado de la comparación, o ``None`` si aún no se
        conoce el tamaño del juego.

    Raises:
        OSError: Si la carpeta de destino no existe o no se puede consultar.
    """
    if not job.size:
        return None
    if options.output_format is OutputFormat.LZ4:
        estimate = job.lz4_estimates.get(options.compression_level) or job.size
        if same_device(job.game_root, job.output.parent):  # lo suelto se enlaza
            estimate -= min(job.lz4_loose_bytes, estimate)
    else:
        estimate = job.estimate_for(options.compression_level, options.is_performance) or job.size
    return SpaceCheck(free_space(job.output.parent), int(estimate * FREE_SPACE_MARGIN))
