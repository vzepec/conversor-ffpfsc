"""Conversión de un juego a LZ4 (formato AMPR) en el PC con las herramientas de ampr_emu.

Pasos: índice del juego → perfil genérico → paquetes LZ4 → verificación byte a byte
contra el original → carpeta final con lo suelto, los paquetes y ``libSceAmpr.sprx``.
El original solo se lee; lo temporal y lo parcial se borran pase lo que pase.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from ffpfsc_converter.config import AMPR_ASSETS_INDEX
from ffpfsc_converter.domain.events import JobStarted
from ffpfsc_converter.domain.models import (
    ConversionJob,
    ConversionOptions,
    ConversionResult,
    SourceKind,
)
from ffpfsc_converter.infrastructure.ampr_tools import parse_pack_progress, parse_pack_summary
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
        write_profile(ws, build_profile(relative_files(ws.root), options.compression_level,
                                        options.cpu_count))
        lines = runner.run(tools.pack_command(paths, options.cpu_count), "compress",
                           parse_pack_progress)
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
