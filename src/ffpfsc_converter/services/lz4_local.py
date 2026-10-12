"""Conversión de un juego a LZ4 (formato AMPR) en el PC con las herramientas de ampr_emu.

Pasos: índice del juego → perfil genérico → paquetes LZ4 → verificación byte a byte
contra el original → carpeta final con lo suelto, los paquetes y ``libSceAmpr.sprx``.
El original solo se lee; lo temporal y lo parcial se borran pase lo que pase.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from ffpfsc_converter.config import AMPR_ASSETS_INDEX, LZ4_MIN_FREE_BYTES
from ffpfsc_converter.domain.events import JobStarted
from ffpfsc_converter.domain.models import (
    ConversionJob,
    ConversionOptions,
    ConversionResult,
    SourceKind,
)
from ffpfsc_converter.infrastructure.ampr_tools import (
    packed_file_total,
    parse_pack_progress,
    parse_pack_summary,
)
from ffpfsc_converter.infrastructure.filesystem import free_space
from ffpfsc_converter.services.ampr_profile import build_profile
from ffpfsc_converter.services.lz4_local_files import (
    Lz4Workspace,
    copy_loose,
    discard,
    finish_folder,
    folder_size,
    relative_files,
    workspace_for,
    write_profile,
)
from ffpfsc_converter.services.lz4_local_steps import (
    Lz4Components,
    StepContext,
    StepFailedError,
    ToolRunner,
    installed_components,
)

MISSING_COMPONENTS_TEXT = ("Faltan los componentes de LZ4. Vuelve a ejecutar el instalador "
                           "con conexión a internet.")
FOLDERS_ONLY_TEXT = "LZ4 solo funciona con carpetas de juego, no con imágenes."
PROFILE_IGNORED_TEXT = ("Se detuvo: iba a empaquetar más archivos de los previstos "
                        "({found} en vez de {expected}).")
DISK_FULL_TEXT = "Se detuvo: el disco de destino se estaba quedando sin espacio."


class Lz4LocalConversion:
    """Convierte un trabajo a carpeta LZ4 publicando el avance como una conversión más."""

    def __init__(self, ctx: StepContext,
                 components: Callable[[], Lz4Components | None] = installed_components) -> None:
        """Guarda el contexto del runner.

        Args:
            ctx (StepContext): Eventos, procesos y cancelación.
            components (Callable[[], Lz4Components | None]): Localiza las herramientas.
        """
        self._ctx = ctx
        self._components = components

    def run(self, job: ConversionJob, options: ConversionOptions) -> ConversionResult:
        """Convierte el trabajo; al terminar bien, ``job.output`` pasa a ser la carpeta.

        Args:
            job (ConversionJob): Juego en carpeta.
            options (ConversionOptions): Nivel LZ4 (``compression_level``) y núcleos.

        Returns:
            ConversionResult: Resultado (con el tamaño de la carpeta si salió bien).
        """
        started = time.monotonic()
        components = self._components()
        if components is None or job.kind is not SourceKind.FOLDER:
            message = MISSING_COMPONENTS_TEXT if components is None else FOLDERS_ONLY_TEXT
            return ConversionResult(False, False, 0.0, message=message)
        ws = workspace_for(job)
        self._ctx.emit(JobStarted(job, f"LZ4 (ampr_emu): {ws.root} → {ws.output}"))
        try:
            done = self._convert(ws, components, options, ToolRunner(self._ctx, job))
            message = "" if done else "cancelado"
        except (OSError, ValueError, StepFailedError) as exc:
            done, message = False, str(exc)
        finally:
            discard(ws)
        elapsed = time.monotonic() - started
        if not done:
            return ConversionResult(False, self._ctx.cancel.is_set(), elapsed, message=message)
        job.output = ws.output
        return ConversionResult(True, False, elapsed, folder_size(ws.output))

    def _convert(self, ws: Lz4Workspace, components: Lz4Components,
                 options: ConversionOptions, runner: ToolRunner) -> bool:
        """Ejecuta los pasos en orden.

        Args:
            ws (Lz4Workspace): Rutas de la conversión.
            components (Lz4Components): Herramientas y biblioteca.
            options (ConversionOptions): Nivel y núcleos.
            runner (ToolRunner): Ejecuta cada herramienta del trabajo.

        Returns:
            bool: ``True`` si terminó; ``False`` si se canceló.

        Raises:
            OSError: Si falla una operación de archivos.
            ValueError: Si ``ampr_pack.py`` no devolvió su resumen.
            StepFailedError: Si una herramienta terminó con error.
        """
        discard(ws)
        ws.work.mkdir(parents=True)
        tools, paths = components.tools, ws.pack_paths
        if not runner.run(tools.index_command(ws.root, paths.index), "scan"):
            return False
        profile = build_profile(relative_files(ws.root), options.compression_level,
                                options.cpu_count)
        write_profile(ws, profile)
        lines = runner.run(tools.pack_command(paths, options.cpu_count), "compress",
                           parse_pack_progress,
                           _pack_guard(len(profile.compress) + len(profile.audio), ws.work))
        if not lines:
            return False
        summary = parse_pack_summary(lines)
        verify = tools.verify_command(paths.output / AMPR_ASSETS_INDEX, ws.root)
        if not runner.run(verify, "verify"):
            return False
        ws.partial.mkdir()
        if not copy_loose(ws, summary.loose_paths, runner.copy_progress()):
            return False
        finish_folder(ws, components.runtime)
        return True


def _pack_guard(expected: int, work: Path) -> Callable[[str], str | None]:
    """Crea el control que detiene ``ampr_pack.py`` si va a empaquetar de más o sin espacio.

    Si el perfil no se aplicara, empaquetaría todo el juego (incluido lo incompresible) y
    podría llenar el disco: se corta en cuanto anuncia cuántos archivos procesará. Además,
    en cada línea de avance se comprueba que queden ``LZ4_MIN_FREE_BYTES`` libres.

    Args:
        expected (int): Archivos en las listas del perfil.
        work (Path): Carpeta de trabajo (en el disco de destino).

    Returns:
        Callable[[str], str | None]: Recibe cada línea; devuelve el motivo para detenerlo.
    """
    def check(line: str) -> str | None:
        """Compara la cantidad anunciada con la prevista.

        Args:
            line (str): Línea de ``ampr_pack.py``.

        Returns:
            str | None: Motivo si anunció más archivos; ``None`` si no.
        """
        found = packed_file_total(line)
        if found is None:
            return None
        if found > expected:
            return PROFILE_IGNORED_TEXT.format(found=found, expected=expected)
        return DISK_FULL_TEXT if free_space(work) < LZ4_MIN_FREE_BYTES else None

    return check
