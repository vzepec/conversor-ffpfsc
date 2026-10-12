"""Cliente de la API HTTP de exfat2ampr, el payload que comprime juegos a AMPR LZ4 en la PS5.

Cada método es una petición independiente (el motor cierra la conexión tras
responder). Las respuestas se convierten a modelos del dominio con
:mod:`~ffpfsc_converter.infrastructure.exfat2ampr.parsing`.
"""
from __future__ import annotations

from ffpfsc_converter.config import E2A_HTTP_PORT, E2A_HTTP_TIMEOUT_SECONDS
from ffpfsc_converter.domain.lz4 import (
    EngineInfo,
    Lz4Check,
    Lz4Destination,
    Lz4Request,
    Lz4Source,
    Lz4Status,
)
from ffpfsc_converter.infrastructure.exfat2ampr import parsing
from ffpfsc_converter.infrastructure.exfat2ampr.transport import (
    BAD_RESPONSE_CODE,
    OK_STATUS,
    E2aEndpoint,
    E2aHttpError,
    E2aTransport,
    as_array,
    as_object,
)


def _flag(value: bool) -> str:
    """Codifica un booleano como lo espera exfat2ampr.

    Args:
        value (bool): Valor a enviar.

    Returns:
        str: ``"1"`` o ``"0"``.
    """
    return "1" if value else "0"


def _source_params(source: Lz4Source, dest_base: str) -> dict[str, str]:
    """Arma los parámetros comunes de ``/api/check`` y ``/api/start``.

    Args:
        source (Lz4Source): Juego a convertir.
        dest_base (str): Carpeta de juegos de la unidad de destino.

    Returns:
        dict[str, str]: ``path``, ``dest`` y ``smp`` (solo en imágenes).
    """
    params = {"path": source.path, "dest": dest_base}
    if source.is_image:
        params["smp"] = source.smp_title or source.title_id
    return params


class E2aClient:
    """Habla con exfat2ampr por HTTP.

    Todos los métodos lanzan ``OSError`` si no hay conexión o se agota el tiempo,
    y :class:`E2aHttpError` si el motor rechaza la orden (``status`` 401 y
    ``code`` ``"pair"`` cuando falta el token o no es válido).
    """

    def __init__(self, host: str, token: str | None = None, port: int = E2A_HTTP_PORT,
                 timeout: float = E2A_HTTP_TIMEOUT_SECONDS) -> None:
        """Prepara el cliente sin conectarse todavía.

        Args:
            host (str): Dirección de la PS5.
            token (str | None): Token de emparejamiento; ``None`` si aún no hay.
            port (int): Puerto de la API de exfat2ampr.
            timeout (float): Segundos de espera de cada petición.
        """
        self._transport = E2aTransport(E2aEndpoint(host, port, token, timeout))

    def hello(self) -> EngineInfo:
        """Comprueba que el motor responde y si el token es válido (no exige token).

        Returns:
            EngineInfo: Versión del motor y estado del emparejamiento.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: Si la respuesta no es válida.
        """
        return parsing.parse_hello(as_object(self._transport.get("/api/hello")))

    def pair(self, pin: str) -> str:
        """Se empareja con el código de 6 dígitos que muestra la PS5.

        Args:
            pin (str): Código de la notificación de exfat2ampr.

        Returns:
            str: Token para las demás peticiones.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: 403 si el código es incorrecto, 429 si está bloqueado por intentos.
        """
        token = as_object(self._transport.post("/api/pair", {"pin": pin})).get("token")
        if not isinstance(token, str) or not token:
            raise E2aHttpError(OK_STATUS, BAD_RESPONSE_CODE, "missing token")
        return token

    def sources(self) -> list[Lz4Source]:
        """Lista los juegos de la consola que el motor puede convertir.

        Returns:
            list[Lz4Source]: Carpetas e imágenes encontradas.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: Si rechaza la petición o la respuesta no es válida.
        """
        return parsing.parse_sources(as_array(self._transport.get("/api/sources")))

    def destinations(self) -> list[Lz4Destination]:
        """Lista las unidades donde puede quedar el juego convertido.

        Returns:
            list[Lz4Destination]: Unidades con su espacio libre.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: Si rechaza la petición o la respuesta no es válida.
        """
        return parsing.parse_destinations(as_array(self._transport.get("/api/destinations")))

    def check(self, source: Lz4Source, dest_base: str) -> Lz4Check:
        """Pide la comprobación previa de un juego contra un destino.

        Args:
            source (Lz4Source): Juego a convertir.
            dest_base (str): Carpeta de juegos de la unidad de destino.

        Returns:
            Lz4Check: Compatibilidad, espacio necesario, errores y avisos.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: Si rechaza la petición o la respuesta no es válida.
        """
        data = self._transport.get("/api/check", _source_params(source, dest_base))
        return parsing.parse_check(as_object(data))

    def start(self, request: Lz4Request) -> int:
        """Pide una conversión; la salida queda en ``request.output_path``.

        Args:
            request (Lz4Request): Juego, destino, nivel y opciones.

        Returns:
            int: Lugar en la cola del motor (``0`` = empieza ya).

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: 400 (``bad_path``, ``dest_unavailable``, ``bad_name``) o
                409 (``queue_full``).
        """
        params = _source_params(request.source, request.dest_base)
        params.update(level=str(request.level), verify=_flag(request.verify),
                      remove=_flag(request.remove_source), overwrite=_flag(request.overwrite))
        position = as_object(self._transport.post("/api/start", params)).get("position")
        return position if isinstance(position, int) and not isinstance(position, bool) else 0

    def state(self) -> Lz4Status:
        """Lee el estado de la conversión en curso (o el último resultado).

        Returns:
            Lz4Status: Estado, avance y motivo del resultado.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: Si rechaza la petición o la respuesta no es válida.
        """
        return parsing.parse_state(as_object(self._transport.get("/api/state")))

    def pause(self) -> None:
        """Pausa la conversión dejando un punto de reanudación.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: Si rechaza la orden.
        """
        self._transport.post("/api/pause")

    def resume(self, dest: str) -> None:
        """Reanuda una conversión en pausa.

        Args:
            dest (str): Carpeta de salida de la conversión en pausa.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: 400 (``cannot resume``) si no hay nada que reanudar ahí.
        """
        self._transport.post("/api/resume", {"dest": dest})

    def cancel(self) -> None:
        """Cancela la conversión en curso (el motor borra la carpeta a medio crear).

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: Si rechaza la orden.
        """
        self._transport.post("/api/cancel")

    def retry(self) -> None:
        """Repite la última conversión fallida.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: 409 (``nothing_to_retry``) si no hay nada que repetir.
        """
        self._transport.post("/api/retry")

    def dismiss(self) -> None:
        """Descarta el último resultado para que el estado vuelva a ``idle``.

        Raises:
            OSError: Si el motor no responde.
            E2aHttpError: 409 (``busy``) si hay una conversión en curso.
        """
        self._transport.post("/api/dismiss")
