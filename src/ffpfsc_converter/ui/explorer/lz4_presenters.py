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
ENGINE_LAUNCHED_TEXT = "exfat2ampr se inició: mira la notificación de la PS5 con el código."
SELECT_ONE_TEXT = "Selecciona UNA carpeta de juego o una imagen .exfat / .ffpkg."
LZ4_BUSY_TEXT = "Ya hay una compresión LZ4 en curso en la PS5: espera a que termine."
OVERWRITE_NEEDED_TEXT = ("Ya hay una conversión de este juego en el destino: activa «Reemplazar "
                         "la conversión anterior» o elige otra unidad.")
REPAIR_TEXT = ("exfat2ampr pidió emparejar la app de nuevo. Vuelve a elegir el juego y pulsa "
               f"«{LZ4_ACTION_TEXT}»: se te pedirá el código.")
ELF_REQUIRED_TEXT = (
    "exfat2ampr no responde en la PS5. La app puede cargarlo por ti, pero necesita el archivo "
    "exfat2ampr.elf, que no viene incluido.\n\nDescárgalo de la página de exfat2ampr (enlace "
    "abajo) y elígelo: la app lo recordará y lo enviará al cargador de ELF de la PS5 (etaHEN) "
    "cuando haga falta.")

_CHECK_ERRORS = {
    "source_missing": "exfat2ampr ya no encuentra el juego en la PS5.",
    "not_game": "exfat2ampr no reconoce un juego de PS5 en esa ruta.",
    "not_ampr": "El juego no usa libSceAmpr: comprimirlo en LZ4 lo dañaría.",
    "game_running": "El juego está abierto en la PS5: ciérralo antes de convertirlo.",
    "dest_missing": "La unidad de destino no está conectada.",
    "dest_readonly": "La unidad de destino no admite escritura.",
    "space_insufficient": "No hay espacio suficiente en la unidad de destino.",
}
#: Códigos de error de ``/api/check`` (exfat2ampr usa los mismos al fallar una conversión).
CHECK_ERROR_CODES = frozenset(_CHECK_ERRORS)
#: Errores que dependen de la unidad elegida (con otra unidad pueden no aplicar).
_DEST_ERRORS = frozenset({"dest_missing", "dest_readonly", "space_insufficient"})
_CHECK_WARNINGS = {
    "fakelib_disabled": "El fakelib del juego está desactivado en ShadowMountPlus: se cambiará "
                        "a «Emuladores» para que cargue el emulador AMPR.",
    "smp_wait_app": "Empezará cuando cierres la aplicación abierta en la PS5 (regla de "
                    "ShadowMountPlus).",
    "smp_wait_game": "Empezará cuando cierres el juego abierto en la PS5 (regla de "
                     "ShadowMountPlus).",
    "already_ampr": "El origen ya está en formato AMPR.",
    "space_low": "Espacio justo: si la unidad se llena, la conversión queda en pausa.",
    ALREADY_EXISTS: "Ya hay una conversión de este juego en el destino.",
}
#: Avisos que ya explica otra parte de la ventana.
_HIDDEN_WARNINGS = frozenset({"ampr_unknown", ALREADY_EXISTS})


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
    Lz4Compat.YES: CompatInfo("ok", "✓ Compatible: el juego usa libSceAmpr.", True),
    Lz4Compat.UNKNOWN: CompatInfo(
        "warn", "No se pudo comprobar la compatibilidad (eboot cifrado). Prueba el juego "
                "antes de borrar el original.", True),
    Lz4Compat.LATER: CompatInfo(
        "warn", "La compatibilidad se comprobará al empezar, al montar la imagen. Si no es "
                "compatible, exfat2ampr se detendrá sin tocar el original.", True),
    Lz4Compat.NO: CompatInfo(
        "bad", "No es compatible: el juego no usa libSceAmpr y comprimirlo lo dañaría. No se "
               "puede convertir.", False),
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
        str: Motivo en español neutro (el código mismo si es desconocido).
    """
    return _CHECK_ERRORS.get(code, f"exfat2ampr no puede convertir el juego ({code}).")


def warning_lines(check: Lz4Check) -> list[str]:
    """Traduce los avisos de ``/api/check`` que la ventana debe mostrar.

    Args:
        check (Lz4Check): Comprobación previa.

    Returns:
        list[str]: Un texto por aviso, sin los que ya explica la compatibilidad.
    """
    return [_CHECK_WARNINGS.get(code, f"Aviso de exfat2ampr: {code}.")
            for code in check.warnings if code not in _HIDDEN_WARNINGS]


def replaces_existing(check: Lz4Check, checked_dest: str, chosen_dest: str) -> bool:
    """Indica si ya hay una conversión del juego en la unidad elegida.

    Args:
        check (Lz4Check): Comprobación previa.
        checked_dest (str): Destino contra el que se hizo la comprobación.
        chosen_dest (str): Destino elegido en la ventana.

    Returns:
        bool: ``True`` si exfat2ampr avisó ``already_exists`` para ese mismo destino.
    """
    return (ALREADY_EXISTS in check.warnings
            and checked_dest.rstrip("/") == chosen_dest.rstrip("/"))


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
    if replaces_existing(check, checked_dest, request.dest_base) and not request.overwrite:
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
    return f"exfat2ampr no puede iniciar la conversión:\n\n{reasons}"


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
        str: Por ejemplo ``"Juego: 48.0 GB · necesita ≈ 30.0 GB (hasta 48.0 GB)"``.
    """
    return (f"Juego: {format_size(check.source_bytes)} · necesita ≈ "
            f"{format_size(check.need_typical)} (hasta {format_size(check.need_max)})")
