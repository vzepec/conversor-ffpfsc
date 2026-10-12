"""Peticiones HTTP a la API de exfat2ampr (puerto 6972) con la biblioteca estándar.

exfat2ampr es un servidor HTTP/1.0 que cierra la conexión tras cada respuesta y
contesta siempre JSON. Los parámetros viajan como formulario
(``application/x-www-form-urlencoded``): en la *query* con ``GET`` y en el cuerpo
con ``POST``. Las rutas protegidas exigen la cabecera ``X-E2A-Token``.
"""
from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass

TOKEN_HEADER = "X-E2A-Token"
BAD_RESPONSE_CODE = "bad_response"
OK_STATUS = 200
_FORM_TYPE = "application/x-www-form-urlencoded"


class E2aHttpError(Exception):
    """exfat2ampr respondió con un código HTTP de error o con algo que no es JSON.

    Attributes:
        status (int): Código HTTP (por ejemplo ``401``, ``409``).
        code (str): Código estable del error (``pair``, ``queue_full``, ``bad_response``…);
            si el motor no lo da, se usa el texto de ``error``.
        error (str): Texto en inglés que dio el motor.
    """

    def __init__(self, status: int, code: str, error: str) -> None:
        """Guarda el detalle de la respuesta rechazada.

        Args:
            status (int): Código HTTP.
            code (str): Código estable del error.
            error (str): Texto del motor.
        """
        super().__init__(f"exfat2ampr respondió {status}: {error or code}")
        self.status = status
        self.code = code
        self.error = error


@dataclass(frozen=True)
class E2aEndpoint:
    """Dónde escucha exfat2ampr y con qué credencial se le habla.

    Attributes:
        host (str): Dirección de la PS5.
        port (int): Puerto de la API.
        token (str | None): Token de emparejamiento; ``None`` si aún no hay.
        timeout (float): Segundos de espera de cada petición.
    """

    host: str
    port: int
    token: str | None
    timeout: float


def _decode(status: int, body: bytes) -> object:
    """Interpreta el cuerpo JSON de una respuesta.

    Args:
        status (int): Código HTTP de la respuesta (para el error).
        body (bytes): Cuerpo recibido.

    Returns:
        object: Valor JSON decodificado.

    Raises:
        E2aHttpError: Con código ``bad_response`` si el cuerpo no es JSON válido.
    """
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise E2aHttpError(status, BAD_RESPONSE_CODE, "invalid JSON") from exc


def as_object(data: object) -> Mapping[str, object]:
    """Exige que la respuesta sea un objeto JSON.

    Args:
        data (object): JSON recibido.

    Returns:
        Mapping[str, object]: El mismo objeto.

    Raises:
        E2aHttpError: Con código ``bad_response`` si no es un objeto.
    """
    if not isinstance(data, Mapping):
        raise E2aHttpError(OK_STATUS, BAD_RESPONSE_CODE, "expected a JSON object")
    return data


def as_array(data: object) -> list[object]:
    """Exige que la respuesta sea una lista JSON.

    Args:
        data (object): JSON recibido.

    Returns:
        list[object]: La misma lista.

    Raises:
        E2aHttpError: Con código ``bad_response`` si no es una lista.
    """
    if not isinstance(data, list):
        raise E2aHttpError(OK_STATUS, BAD_RESPONSE_CODE, "expected a JSON array")
    return data


def _http_error(exc: urllib.error.HTTPError) -> E2aHttpError:
    """Convierte una respuesta no 2xx en un ``E2aHttpError`` con el detalle del motor.

    Args:
        exc (urllib.error.HTTPError): Error que lanzó ``urllib``.

    Returns:
        E2aHttpError: Error con el ``code`` y el ``error`` del JSON, si lo había.
    """
    try:
        data = _decode(exc.code, exc.read())
    except (E2aHttpError, OSError):
        data = {}
    if not isinstance(data, Mapping):
        data = {}
    error = data.get("error")
    code = data.get("code")
    error_text = error if isinstance(error, str) else str(exc.reason or "")
    return E2aHttpError(exc.code, code if isinstance(code, str) else error_text, error_text)


class E2aTransport:
    """Envía peticiones a exfat2ampr y devuelve el JSON de la respuesta.

    No usa los *proxies* del entorno: la PS5 está en la red local.
    """

    def __init__(self, endpoint: E2aEndpoint) -> None:
        """Prepara el transporte sin abrir conexiones.

        Args:
            endpoint (E2aEndpoint): Dirección, puerto, token y tiempo de espera.
        """
        self.endpoint = endpoint
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(self, path: str, params: Mapping[str, str] | None = None) -> object:
        """Hace un ``GET`` con los parámetros en la *query*.

        Args:
            path (str): Ruta de la API (``/api/state``).
            params (Mapping[str, str] | None): Parámetros del formulario.

        Returns:
            object: JSON de la respuesta.

        Raises:
            OSError: Si no hay conexión, se agota el tiempo o la respuesta no es HTTP.
            E2aHttpError: Si el motor responde con un error o con algo que no es JSON.
        """
        query = urllib.parse.urlencode(params or {})
        return self._send(urllib.request.Request(
            self._url(path) + (f"?{query}" if query else ""), method="GET",
        ))

    def post(self, path: str, params: Mapping[str, str] | None = None) -> object:
        """Hace un ``POST`` con los parámetros en el cuerpo.

        Args:
            path (str): Ruta de la API (``/api/start``).
            params (Mapping[str, str] | None): Parámetros del formulario.

        Returns:
            object: JSON de la respuesta.

        Raises:
            OSError: Si no hay conexión, se agota el tiempo o la respuesta no es HTTP.
            E2aHttpError: Si el motor responde con un error o con algo que no es JSON.
        """
        body = urllib.parse.urlencode(params or {}).encode("ascii")
        request = urllib.request.Request(self._url(path), data=body, method="POST")
        request.add_header("Content-Type", _FORM_TYPE)
        return self._send(request)

    def _url(self, path: str) -> str:
        """Construye la dirección completa de una ruta de la API.

        Args:
            path (str): Ruta que empieza con ``/``.

        Returns:
            str: URL ``http://host:puerto/ruta``.
        """
        host = self.endpoint.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"  # una IPv6 va entre corchetes dentro de una URL
        return f"http://{host}:{self.endpoint.port}{path}"

    def _send(self, request: urllib.request.Request) -> object:
        """Envía una petición con el token (si lo hay) y decodifica la respuesta.

        Args:
            request (urllib.request.Request): Petición ya construida.

        Returns:
            object: JSON de la respuesta.

        Raises:
            OSError: Si no hay conexión, se agota el tiempo o la respuesta no es HTTP.
            E2aHttpError: Si el motor responde con un error o con algo que no es JSON.
        """
        if self.endpoint.token:
            request.add_header(TOKEN_HEADER, self.endpoint.token)
        try:
            with self._opener.open(request, timeout=self.endpoint.timeout) as response:
                return _decode(response.status, response.read())
        except urllib.error.HTTPError as exc:
            raise _http_error(exc) from exc
        except http.client.HTTPException as exc:
            raise OSError(f"respuesta HTTP no válida de exfat2ampr: {exc!r}") from exc
