"""Preferencias que la app recuerda entre sesiones: opciones de conversión y ventana.

Las funciones ``*_from`` son puras (validan lo guardado, que puede venir de una
versión anterior o haberse editado a mano); ``save_*`` lo escriben en los ajustes.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from ffpfsc_converter.domain.models import OutputFormat
from ffpfsc_converter.infrastructure.settings_store import save_settings

#: Claves de los ajustes.
_PRESET, _CORES, _VERIFY = "convert_preset", "convert_cores", "convert_verify"
_PERFORMANCE = "convert_ps5_performance"
_LZ4_VERIFY = "convert_lz4_verify"
_FORMAT = "convert_output_format"
_OUTPUT = "output_dir"
_SIZE, _ZOOMED, _VIEW = "window_size", "window_zoomed", "last_view"


@dataclass(frozen=True)
class ConvertPreferences:
    """Opciones de conversión recordadas.

    Attributes:
        preset (str | None): Etiqueta del modo elegido; ``None`` = el predeterminado.
        cores (int | None): Núcleos elegidos; ``None`` = todos.
        full_verify (bool): Verificación completa activada (``.ffpfsc``).
        lz4_verify (bool): Verificación completa de LZ4 (activada salvo que se apague).
        performance (bool): «Rendimiento en la PS5» activado.
        output_format (OutputFormat): ``.ffpfsc`` o LZ4.
        output_dir (Path | None): Carpeta de destino; ``None`` = junto a cada juego.
    """

    preset: str | None
    cores: int | None
    full_verify: bool
    lz4_verify: bool
    performance: bool
    output_format: OutputFormat
    output_dir: Path | None


@dataclass(frozen=True)
class WindowPreferences:
    """Estado de la ventana recordado.

    Attributes:
        size (tuple[int, int] | None): Ancho y alto; ``None`` = el tamaño inicial.
        zoomed (bool): ``True`` si estaba maximizada.
        view (str): Última vista abierta (``"convert"`` o ``"ps5"``).
    """

    size: tuple[int, int] | None
    zoomed: bool
    view: str


def convert_from(settings: Mapping[str, object], presets: Collection[str],
                 cpu_total: int) -> ConvertPreferences:
    """Valida las opciones de conversión guardadas.

    Args:
        settings (Mapping[str, object]): Ajustes leídos.
        presets (Collection[str]): Etiquetas de modo válidas.
        cpu_total (int): Núcleos del equipo (los guardados se limitan a ese máximo).

    Returns:
        ConvertPreferences: Opciones válidas (lo inválido vuelve al valor predeterminado).
    """
    preset = settings.get(_PRESET)
    cores = settings.get(_CORES)
    output = settings.get(_OUTPUT)
    folder = Path(output) if isinstance(output, str) and output else None
    return ConvertPreferences(
        preset=preset if isinstance(preset, str) and preset in presets else None,
        cores=min(max(cores, 1), cpu_total) if isinstance(cores, int) else None,
        full_verify=settings.get(_VERIFY) is True,
        lz4_verify=settings.get(_LZ4_VERIFY) is not False,
        performance=settings.get(_PERFORMANCE) is True,
        output_format=_format_from(settings.get(_FORMAT)),
        output_dir=folder if folder is not None and folder.is_dir() else None,
    )


def window_from(settings: Mapping[str, object], minimum: tuple[int, int],
                screen: tuple[int, int], views: Collection[str]) -> WindowPreferences:
    """Valida el tamaño y la vista guardados para que la ventana quepa en la pantalla.

    Args:
        settings (Mapping[str, object]): Ajustes leídos.
        minimum (tuple[int, int]): Tamaño mínimo de la ventana.
        screen (tuple[int, int]): Tamaño de la pantalla actual.
        views (Collection[str]): Vistas existentes.

    Returns:
        WindowPreferences: Tamaño (o ``None`` si no sirve), maximizado y vista.
    """
    raw = settings.get(_SIZE)
    size: tuple[int, int] | None = None
    if isinstance(raw, list) and len(raw) == 2 and all(isinstance(v, int) for v in raw):
        size = (raw[0], raw[1])
    fits = size is not None and all(low <= value <= high for low, value, high in
                                    zip(minimum, size, screen, strict=True))
    view = settings.get(_VIEW)
    return WindowPreferences(
        size=size if fits else None,
        zoomed=settings.get(_ZOOMED) is True,
        view=view if isinstance(view, str) and view in views else next(iter(views)),
    )


def save_convert(preset: str, cores: int, full_verify: bool, performance: bool) -> None:
    """Guarda las opciones de conversión elegidas.

    Args:
        preset (str): Etiqueta del modo.
        cores (int): Núcleos.
        full_verify (bool): Verificación completa.
        performance (bool): «Rendimiento en la PS5».
    """
    save_settings({_PRESET: preset, _CORES: cores, _VERIFY: full_verify,
                   _PERFORMANCE: performance})


def save_lz4_verify(full_verify: bool) -> None:
    """Guarda si se verifica el resultado de las conversiones LZ4.

    Args:
        full_verify (bool): Verificación completa de LZ4.
    """
    save_settings({_LZ4_VERIFY: full_verify})


def save_output_format(output_format: OutputFormat) -> None:
    """Guarda el formato de salida elegido.

    Args:
        output_format (OutputFormat): ``.ffpfsc`` o LZ4.
    """
    save_settings({_FORMAT: output_format.value})


def _format_from(value: object) -> OutputFormat:
    """Valida el formato guardado (un valor desconocido vuelve a ``.ffpfsc``).

    Args:
        value (object): Valor leído de los ajustes.

    Returns:
        OutputFormat: Formato válido.
    """
    return next((f for f in OutputFormat if f.value == value), OutputFormat.FFPFSC)


def save_output_dir(folder: Path | None) -> None:
    """Guarda la carpeta de destino (``None`` = junto a cada juego).

    Args:
        folder (Path | None): Carpeta elegida.
    """
    save_settings({_OUTPUT: str(folder) if folder else ""})


def save_window(size: tuple[int, int], zoomed: bool, view: str) -> None:
    """Guarda el tamaño de la ventana, si estaba maximizada y la vista abierta.

    Args:
        size (tuple[int, int]): Ancho y alto actuales.
        zoomed (bool): ``True`` si está maximizada.
        view (str): Vista abierta.
    """
    save_settings({_SIZE: list(size), _ZOOMED: zoomed, _VIEW: view})
