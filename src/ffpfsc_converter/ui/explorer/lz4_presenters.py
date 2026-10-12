"""Textos de la compresión LZ4 en la PS5 (exfat2ampr): comprobación previa, destinos y resumen.

Funciones puras: exfat2ampr responde con códigos estables en inglés y aquí se
traducen a español neutro para la ventana de compresión y sus avisos.
"""
from __future__ import annotations

from dataclasses import dataclass

from ffpfsc_converter.domain.lz4 import Lz4Check, Lz4Compat, Lz4Request, Lz4Source
from ffpfsc_converter.formatting import format_size

LZ4_ACTION_TEXT = "Comprimir LZ4 en la PS5…"
LZ4_SHORT_TEXT = "LZ4…"
LZ4_TITLE = "Comprimir LZ4 en la PS5"
#: Aviso de ``/api/check`` cuando ya hay una conversión del juego en el destino.
ALREADY_EXISTS = "already_exists"
ENGINE_LAUNCHED_TEXT = "Iniciando exfat2ampr en la PS5…"
SELECT_ONE_TEXT = "Selecciona un solo juego (carpeta o imagen)."
LZ4_BUSY_TEXT = "Ya hay una compresión en curso. Espera a que termine."
OVERWRITE_NEEDED_TEXT = "Ya está comprimido en esta unidad. Activa «Reemplazar» o elige otra."
REPAIR_TEXT = f"Hay que volver a emparejar. Pulsa «{LZ4_ACTION_TEXT}» otra vez."
ELF_REQUIRED_TEXT = (
    "Para comprimir en la PS5 hace falta exfat2ampr, que no viene con la app.\n\n"
    "Descarga exfat2ampr.elf del enlace y elígelo. La app lo recordará.")
_UNKNOWN_ERROR_TEXT = "No se puede comprimir este juego."

_CHECK_ERRORS = {
    "source_missing": "El juego ya no está en la PS5.",
    "not_game": "No es un juego de PS5.",
    "not_ampr": "Este juego no es compatible.",
    "game_running": "El juego está abierto en la PS5: ciérralo.",
    "dest_missing": "La unidad de destino no está conectada.",
    "dest_readonly": "No se puede escribir en la unidad de destino.",
    "space_insufficient": "No hay espacio suficiente en la unidad de destino.",
}
#: Códigos de error de ``/api/check`` (exfat2ampr usa los mismos al fallar una conversión).
CHECK_ERROR_CODES = frozenset(_CHECK_ERRORS)
#: Errores que dependen de la unidad elegida (con otra unidad pueden no aplicar).
_DEST_ERRORS = frozenset({"dest_missing", "dest_readonly", "space_insufficient"})
#: Avisos que se muestran; el resto (``fakelib_disabled``, ``ampr_unknown``, códigos
#: nuevos…) no exige nada al usuario y solo queda en el registro.
_CHECK_WARNINGS = {
    "smp_wait_app": "Empezará cuando cierres la aplicación abierta en la PS5.",
    "smp_wait_game": "Empezará cuando cierres el juego abierto en la PS5.",
    "already_ampr": "Este juego ya está comprimido.",
    "space_low": "Espacio justo: si se llena, la compresión se pausará.",
}


@dataclass(frozen=True)
class CompatInfo:
    """Compatibilidad del juego con LZ4 lista para mostrar.

    Attributes:
        kind (str): Color: ``"ok"``, ``"warn"`` o ``"bad"``.
        text (str): Explicación.
        can_start (bool): ``False`` si no tiene sentido iniciar la conversión.
    """

    kind: str
    text: str
    can_start: bool


_COMPAT = {
    Lz4Compat.YES: CompatInfo("ok", "✓ Compatible", True),
    Lz4Compat.UNKNOWN: CompatInfo(
        "warn", "Compatibilidad sin confirmar: prueba el juego antes de borrar el original.",
        True),
    Lz4Compat.LATER: CompatInfo("warn", "La compatibilidad se comprobará al empezar.", True),
    Lz4Compat.NO: CompatInfo("bad", "✗ No compatible", False),
}


def compat_info(compat: Lz4Compat) -> CompatInfo:
    """Describe si el juego puede usar el formato AMPR.

    Args:
        compat (Lz4Compat): Resultado de exfat2ampr.

    Returns:
        CompatInfo: Color, texto y si se puede iniciar.
    """
    return _COMPAT[compat]


def check_error_text(code: str) -> str:
    """Traduce un código de error de ``/api/check``.

    Args:
        code (str): Por ejemplo ``"game_running"``.

    Returns:
        str: Motivo en español neutro (uno genérico si el código es desconocido).
    """
    return _CHECK_ERRORS.get(code, _UNKNOWN_ERROR_TEXT)


def warning_lines(check: Lz4Check) -> list[str]:
    """Traduce los avisos de ``/api/check`` que la ventana debe mostrar.

    Args:
        check (Lz4Check): Comprobación previa.

    Returns:
        list[str]: Un texto por aviso que le sirve al usuario (los demás se omiten).
    """
    return [_CHECK_WARNINGS[code] for code in check.warnings if code in _CHECK_WARNINGS]


def replaces_existing(check: Lz4Check, checked_dest: str, request: Lz4Request) -> bool:
    """Indica si ya hay una conversión del juego donde se guardará la nueva.

    exfat2ampr comprueba ``<destino>/<TITLE_ID>``; si la salida usa otro nombre (porque
    esa ruta es el propio original), su aviso no aplica.

    Args:
        check (Lz4Check): Comprobación previa.
        checked_dest (str): Destino contra el que se hizo la comprobación.
        request (Lz4Request): Conversión elegida en la ventana.

    Returns:
        bool: ``True`` si exfat2ampr avisó ``already_exists`` para esa misma carpeta.
    """
    return (ALREADY_EXISTS in check.warnings and not request.name
            and checked_dest.rstrip("/") == request.dest_base.rstrip("/"))


def start_blockers(check: Lz4Check, checked_dest: str, request: Lz4Request) -> list[str]:
    """Elige los motivos que impiden empezar con las opciones elegidas.

    La comprobación se hizo contra ``checked_dest``; si se elige otra unidad, sus
    errores de espacio o escritura no aplican (exfat2ampr vuelve a comprobar al empezar).

    Args:
        check (Lz4Check): Comprobación previa.
        checked_dest (str): Destino contra el que se hizo la comprobación.
        request (Lz4Request): Conversión elegida en la ventana.

    Returns:
        list[str]: Motivos en español (vacía si se puede empezar).
    """
    same = checked_dest.rstrip("/") == request.dest_base.rstrip("/")
    errors = [check_error_text(code) for code in check.errors
              if same or code not in _DEST_ERRORS]
    compat = compat_info(check.compatible)
    if not compat.can_start and not errors:
        errors.append(compat.text)
    if replaces_existing(check, checked_dest, request) and not request.overwrite:
        errors.append(OVERWRITE_NEEDED_TEXT)
    return errors


def rejection_text(check: Lz4Check) -> str:
    """Explica por qué exfat2ampr no inició la conversión.

    Args:
        check (Lz4Check): Comprobación final con errores.

    Returns:
        str: Encabezado y un motivo por línea.
    """
    reasons = "\n".join(f"• {check_error_text(code)}" for code in check.errors)
    return f"No se pudo empezar:\n\n{reasons}"


def game_text(source: Lz4Source) -> str:
    """Resume el juego elegido.

    Args:
        source (Lz4Source): Juego.

    Returns:
        str: Por ejemplo ``"Astro Bot · PPSA01234 · versión 01.000"``.
    """
    parts = [source.title or source.title_id, source.title_id]
    if source.version:
        parts.append(f"versión {source.version}")
    return " · ".join(p for p in dict.fromkeys(parts) if p)


def size_text(check: Lz4Check) -> str:
    """Resume el tamaño del juego y el espacio que suele necesitar la conversión.

    Args:
        check (Lz4Check): Comprobación previa.

    Returns:
        str: Por ejemplo ``"Ocupa 48.0 GB · necesita unos 30.0 GB libres"``.
    """
    return (f"Ocupa {format_size(check.source_bytes)} · necesita unos "
            f"{format_size(check.need_typical)} libres")
