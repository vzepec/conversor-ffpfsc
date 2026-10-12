"""Textos de la compresión LZ4 en la PS5: destinos, cambios exactos y emparejamiento.

Funciones puras usadas por la ventana de compresión y por el coordinador.
"""
from __future__ import annotations

from collections.abc import Sequence

from ffpfsc_converter.domain.lz4 import Lz4Destination, Lz4Request
from ffpfsc_converter.formatting import format_size

_KIND_NAMES = {"internal": "Interno", "usb": "USB", "extended": "Ampliado"}


def destination_name(dest: Lz4Destination) -> str:
    """Nombra una unidad de destino como la ve el usuario.

    Args:
        dest (Lz4Destination): Unidad.

    Returns:
        str: ``"Interno"``, ``"USB 1"``, ``"Ampliado"``, ``"Ampliado 2"``… o la etiqueta
        de exfat2ampr si el tipo es desconocido.
    """
    name = _KIND_NAMES.get(dest.kind)
    if name is None:
        return dest.label or dest.base
    if dest.kind == "usb":
        return f"{name} {max(dest.index, 0) + 1}"
    return name if dest.index <= 0 else f"{name} {dest.index + 1}"


def destination_label(dest: Lz4Destination) -> str:
    """Describe una unidad de destino con su espacio libre.

    Args:
        dest (Lz4Destination): Unidad.

    Returns:
        str: Por ejemplo ``"Interno · 180.0 GB libres"``.
    """
    return f"{destination_name(dest)} · {format_size(dest.free)} libres"


def writable_destinations(destinations: Sequence[Lz4Destination]) -> list[Lz4Destination]:
    """Filtra las unidades donde se puede guardar el juego convertido.

    Args:
        destinations (Sequence[Lz4Destination]): Unidades de la PS5.

    Returns:
        list[Lz4Destination]: Solo las escribibles, en el mismo orden.
    """
    return [d for d in destinations if d.writable]


def summary_lines(request: Lz4Request, replaces: bool) -> list[str]:
    """Enumera los cambios exactos que hará exfat2ampr en la PS5.

    Args:
        request (Lz4Request): Conversión que se pedirá.
        replaces (bool): ``True`` si ya existe una conversión en la carpeta de salida.

    Returns:
        list[str]: Rutas que se crean, reemplazan o borran, una por línea.
    """
    verb = "Se REEMPLAZARÁ" if replaces and request.overwrite else "Se creará"
    lines = [f"{verb} {request.output_path}"]
    if request.remove_source:
        lines.append(f"Se BORRARÁ el original al terminar: {request.source.path}")
    else:
        lines.append(f"Se conserva el original: {request.source.path}")
    return lines


def remove_confirmation(request: Lz4Request) -> str:
    """Pide confirmar que se borrará el original tras convertir.

    Args:
        request (Lz4Request): Conversión con ``remove_source``.

    Returns:
        str: Pregunta con las rutas exactas.
    """
    return (f"Al terminar se BORRARÁ de la PS5:\n\n{request.source.path}\n\n"
            f"El juego quedará solo en:\n{request.output_path}\n\n"
            "No se puede deshacer. ¿Continuar?")


def pairing_text(retry: bool) -> str:
    """Pide el código de emparejamiento de exfat2ampr.

    Args:
        retry (bool): ``True`` si el código anterior fue incorrecto.

    Returns:
        str: Instrucción breve para la ventana de emparejamiento.
    """
    if retry:
        return "Código incorrecto. Escribe el de la notificación de la PS5:"
    return "Escribe el código de 6 dígitos que muestra la notificación de la PS5:"
