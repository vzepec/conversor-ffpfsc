"""Conversión de las respuestas JSON de exfat2ampr a los modelos del dominio.

Funciones puras y tolerantes: un campo ausente o de otro tipo toma un valor por
defecto en lugar de fallar, porque el motor puede agregar o quitar campos entre
versiones y la app solo usa una parte de ellos.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from ffpfsc_converter.domain.lz4 import (
    EngineInfo,
    Lz4Check,
    Lz4Compat,
    Lz4Destination,
    Lz4JobState,
    Lz4Source,
    Lz4Status,
)

_TRUE_TEXTS = frozenset({"1", "t", "true", "o", "on", "yes"})


def _text(data: Mapping[str, object], key: str) -> str:
    """Lee un campo de texto.

    Args:
        data (Mapping[str, object]): Objeto JSON.
        key (str): Nombre del campo.

    Returns:
        str: El texto, o ``""`` si falta o no es una cadena.
    """
    value = data.get(key)
    return value if isinstance(value, str) else ""


def _number(data: Mapping[str, object], key: str, default: int = 0) -> int:
    """Lee un campo numérico entero.

    Args:
        data (Mapping[str, object]): Objeto JSON.
        key (str): Nombre del campo.
        default (int): Valor si falta o no es un número.

    Returns:
        int: El número truncado a entero.
    """
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)


def _real(data: Mapping[str, object], key: str) -> float:
    """Lee un campo numérico con decimales.

    Args:
        data (Mapping[str, object]): Objeto JSON.
        key (str): Nombre del campo.

    Returns:
        float: El número, o ``0.0`` si falta o no es un número.
    """
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _flag(data: Mapping[str, object], key: str) -> bool:
    """Lee un campo booleano (también acepta ``1``/``0`` y ``"1"``/``"t"``).

    Args:
        data (Mapping[str, object]): Objeto JSON.
        key (str): Nombre del campo.

    Returns:
        bool: ``True`` solo si el valor representa verdadero.
    """
    value = data.get(key)
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_TEXTS
    return isinstance(value, (bool, int, float)) and bool(value)


def _texts(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    """Lee una lista de cadenas.

    Args:
        data (Mapping[str, object]): Objeto JSON.
        key (str): Nombre del campo.

    Returns:
        tuple[str, ...]: Las cadenas de la lista (se descarta lo demás).
    """
    value = data.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _objects(items: Iterable[object]) -> list[Mapping[str, object]]:
    """Filtra los objetos JSON de una lista.

    Args:
        items (Iterable[object]): Elementos de una lista JSON.

    Returns:
        list[Mapping[str, object]]: Solo los elementos que son objetos.
    """
    return [item for item in items if isinstance(item, Mapping)]


def parse_hello(data: Mapping[str, object]) -> EngineInfo:
    """Convierte la respuesta de ``/api/hello``.

    Args:
        data (Mapping[str, object]): Objeto JSON recibido.

    Returns:
        EngineInfo: Versión del motor y si el token es válido.
    """
    return EngineInfo(version=_text(data, "version"), paired=_flag(data, "paired"))


def parse_source(data: Mapping[str, object]) -> Lz4Source:
    """Convierte un elemento de ``/api/sources``.

    Args:
        data (Mapping[str, object]): Objeto JSON de un juego.

    Returns:
        Lz4Source: Juego que exfat2ampr puede convertir.
    """
    return Lz4Source(
        path=_text(data, "path"), kind=_text(data, "type") or "folder",
        title_id=_text(data, "title_id"), title=_text(data, "title"),
        version=_text(data, "version"), smp_title=_text(data, "smp_title"),
    )


def parse_sources(items: Iterable[object]) -> list[Lz4Source]:
    """Convierte la lista de ``/api/sources`` (se omiten elementos sin ruta).

    Args:
        items (Iterable[object]): Lista JSON recibida.

    Returns:
        list[Lz4Source]: Juegos en el orden que informa el motor.
    """
    sources = [parse_source(item) for item in _objects(items)]
    return [source for source in sources if source.path]


def parse_destinations(items: Iterable[object]) -> list[Lz4Destination]:
    """Convierte la lista de ``/api/destinations`` (se omiten elementos sin ruta).

    Args:
        items (Iterable[object]): Lista JSON recibida.

    Returns:
        list[Lz4Destination]: Unidades donde puede quedar el juego convertido.
    """
    return [
        Lz4Destination(
            base=_text(item, "path"), kind=_text(item, "kind"),
            index=_number(item, "index", -1), label=_text(item, "label"),
            total=_number(item, "total"), free=_number(item, "free"),
            writable=_flag(item, "writable"), reason=_text(item, "reason"),
        )
        for item in _objects(items) if _text(item, "path")
    ]


def parse_check(data: Mapping[str, object]) -> Lz4Check:
    """Convierte la respuesta de ``/api/check``.

    Args:
        data (Mapping[str, object]): Objeto JSON recibido.

    Returns:
        Lz4Check: Comprobación previa; una compatibilidad desconocida queda en ``UNKNOWN``.
    """
    try:
        compatible = Lz4Compat(_text(data, "compatible"))
    except ValueError:
        compatible = Lz4Compat.UNKNOWN
    return Lz4Check(
        title_id=_text(data, "title_id"), title=_text(data, "title"),
        source_bytes=_number(data, "source_bytes"), need_typical=_number(data, "need_typical"),
        need_max=_number(data, "need_max"), dest_free=_number(data, "dest_free"),
        dest_total=_number(data, "dest_total"), compatible=compatible,
        errors=_texts(data, "errors"), warnings=_texts(data, "warnings"),
    )


def _job_state(data: Mapping[str, object]) -> Lz4JobState:
    """Interpreta el campo ``state`` de ``/api/state``.

    Args:
        data (Mapping[str, object]): Objeto JSON recibido.

    Returns:
        Lz4JobState: El estado, o ``IDLE`` si es desconocido.
    """
    try:
        return Lz4JobState(_text(data, "state"))
    except ValueError:
        return Lz4JobState.IDLE


def parse_state(data: Mapping[str, object]) -> Lz4Status:
    """Convierte la respuesta de ``/api/state``.

    Args:
        data (Mapping[str, object]): Objeto JSON recibido.

    Returns:
        Lz4Status: Estado del motor; un ``eta_seconds`` negativo queda en ``None``.
    """
    eta = _number(data, "eta_seconds", -1)
    return Lz4Status(
        state=_job_state(data), phase=_text(data, "phase"),
        percent=max(0, min(100, _number(data, "percent"))),
        bytes_done=_number(data, "bytes_done"), bytes_total=_number(data, "bytes_total"),
        speed_bps=_real(data, "speed_bps"),
        eta_seconds=eta if eta >= 0 else None,
        code=_text(data, "code"), message=_text(data, "message"),
        title_id=_text(data, "title_id"), title=_text(data, "title"), dest=_text(data, "dest"),
        waiting=_flag(data, "waiting"), resumable=_flag(data, "resumable"),
        queue=_texts(data, "queue"),
    )
