"""Datos del exfat2ampr falso: peticiones, juegos, unidades y comprobación previa.

Lo usa :mod:`e2a_fake_logic`; los tests normalmente solo importan
:class:`e2a_fake.FakeE2aEngine` y, si quieren otros juegos, :class:`FakeGame`.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

GIB = 1024**3
#: Fracción del tamaño original que ocupa "normalmente" un juego comprimido.
TYPICAL_RATIO = 0.6


@dataclass(frozen=True)
class FakeGame:
    """Juego que el motor falso informa en ``/api/sources``.

    Attributes:
        path (str): Carpeta o imagen.
        title_id (str): Title ID.
        title (str): Nombre.
        kind (str): ``"folder"`` o ``"image"``.
        compatible (str): ``yes``, ``no`` (da ``not_ampr``), ``unknown`` o ``later``.
        size (int): Bytes del juego.
        smp_title (str): Title ID de montaje (solo imágenes).
    """

    path: str
    title_id: str
    title: str = "Juego de prueba"
    kind: str = "folder"
    compatible: str = "yes"
    size: int = 10 * GIB
    smp_title: str = ""


@dataclass(frozen=True)
class FakeDestination:
    """Unidad que el motor falso informa en ``/api/destinations``.

    Attributes:
        base (str): Carpeta de juegos de la unidad.
        kind (str): ``internal``, ``usb`` o ``extended``.
        index (int): Número de la unidad; ``-1`` en la interna.
        free (int): Bytes libres.
        total (int): Bytes totales.
        writable (bool): ``False`` da ``dest_readonly``.
    """

    base: str
    kind: str
    index: int
    free: int
    total: int = 1000 * GIB
    writable: bool = True


@dataclass(frozen=True)
class FakeRequest:
    """Petición recibida por el motor falso (se guardan todas para los tests).

    Attributes:
        method (str): ``GET`` o ``POST``.
        path (str): Ruta sin la *query*.
        params (dict[str, str]): Parámetros del cuerpo (o de la *query* si no hay cuerpo).
        token (str | None): Valor de ``X-E2A-Token`` (o de ``?t=``).
    """

    method: str
    path: str
    params: dict[str, str] = field(default_factory=dict)
    token: str | None = None


@dataclass(frozen=True)
class FakeReply:
    """Respuesta del motor falso.

    Attributes:
        status (int): Código HTTP.
        body (object): Valor que se envía como JSON.
    """

    status: int
    body: object


def error_reply(status: int, error: str, code: str = "") -> FakeReply:
    """Arma una respuesta de error con el formato del motor.

    Returns:
        FakeReply: ``{"error": …}`` y, si se da, ``"code"``.
    """
    return FakeReply(status, {"error": error, "code": code} if code else {"error": error})


GAME_OK = FakeGame("/data/homebrew/PPSA01234", "PPSA01234", "Juego compatible")
GAME_NOT_AMPR = FakeGame("/data/homebrew/PPSA09999", "PPSA09999", "Juego sin AMPR",
                         compatible="no")
GAME_IMAGE = FakeGame("/mnt/usb0/homebrew/Juego.exfat", "PPSA05555", "Juego en imagen",
                      kind="image", compatible="later", smp_title="PPSA05555")
DEST_INTERNAL = FakeDestination("/data/homebrew", "internal", -1, free=200 * GIB)
#: Unidad casi llena: un juego de 10 GiB da ``space_insufficient``.
DEST_USB = FakeDestination("/mnt/usb0/homebrew", "usb", 0, free=4 * GIB)


@dataclass
class FakeConsoleData:
    """Contenido de la consola falsa (lo comparten la API y los trabajos).

    Attributes:
        games (dict[str, FakeGame]): Juegos por ruta.
        destinations (list[FakeDestination]): Unidades.
        existing (set[str]): Carpetas de salida que ya existen (dan ``already_exists``).
        running_game (str): Title ID del juego abierto en la consola (da ``game_running``).
    """

    games: dict[str, FakeGame] = field(default_factory=dict)
    destinations: list[FakeDestination] = field(default_factory=list)
    existing: set[str] = field(default_factory=set)
    running_game: str = ""

    def destination(self, base: str) -> FakeDestination | None:
        """Busca una unidad por su carpeta de juegos.

        Returns:
            FakeDestination | None: La unidad, o ``None`` si no existe.
        """
        return next((d for d in self.destinations if d.base == base.rstrip("/")), None)


def output_path(dest_base: str, name: str) -> str:
    """Calcula la carpeta que crea el motor (``<dest>/<name>``).

    Returns:
        str: Ruta de salida.
    """
    return f"{dest_base.rstrip('/')}/{name}"


def source_json(game: FakeGame) -> dict[str, object]:
    """Representa un juego como lo hace ``/api/sources``.

    Returns:
        dict[str, object]: Objeto JSON (con campos extra que el cliente ignora).
    """
    data: dict[str, object] = {
        "type": game.kind, "path": game.path, "title_id": game.title_id,
        "title": game.title, "version": "01.000", "ampr": False, "partial": False,
        "selectable": True, "image": "",
    }
    if game.kind == "image":
        data["smp_title"] = game.smp_title
    return data


def destination_json(dest: FakeDestination) -> dict[str, object]:
    """Representa una unidad como lo hace ``/api/destinations``.

    Returns:
        dict[str, object]: Objeto JSON.
    """
    return {
        "path": dest.base, "mount": dest.base.rsplit("/", 1)[0], "device": "fake",
        "kind": dest.kind, "index": dest.index, "label": f"{dest.kind} {dest.index}",
        "fstype": "exfat", "total": dest.total, "free": dest.free,
        "writable": dest.writable, "reason": "" if dest.writable else "read_only",
        "read_mbps": -1, "write_mbps": -1,
    }


def _check_codes(console: FakeConsoleData, game: FakeGame,
                 dest: FakeDestination | None) -> tuple[list[str], list[str]]:
    """Calcula los errores y avisos de la comprobación previa de un juego.

    Returns:
        tuple[list[str], list[str]]: Errores y avisos.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if game.compatible == "no":
        errors.append("not_ampr")
    if console.running_game == game.title_id:
        errors.append("game_running")
    if dest is None:
        return [*errors, "dest_missing"], warnings
    if not dest.writable:
        errors.append("dest_readonly")
    if dest.free < int(game.size * TYPICAL_RATIO):
        errors.append("space_insufficient")
    elif dest.free < game.size:
        warnings.append("space_low")
    default = output_path(dest.base, game.title_id)
    if default in console.existing or default == game.path.rstrip("/"):
        warnings.append("already_exists")  # el real mira si la carpeta existe: el original cuenta
    return errors, warnings


def check_json(console: FakeConsoleData, params: Mapping[str, str]) -> dict[str, object]:
    """Responde ``/api/check`` con errores y avisos coherentes con los datos.

    Returns:
        dict[str, object]: Objeto JSON de la comprobación.
    """
    game = console.games.get(params.get("path", ""))
    dest = console.destination(params.get("dest", ""))
    if game is None:
        return {"title_id": "", "title": "", "source_bytes": 0, "need_typical": 0,
                "need_max": 0, "dest_free": 0, "dest_total": 0, "compatible": "unknown",
                "errors": ["source_missing"], "warnings": []}
    errors, warnings = _check_codes(console, game, dest)
    return {
        "title_id": game.title_id, "title": game.title, "source_bytes": game.size,
        "need_typical": int(game.size * TYPICAL_RATIO), "need_max": game.size,
        "dest_free": dest.free if dest else 0, "dest_total": dest.total if dest else 0,
        "compatible": game.compatible, "errors": errors, "warnings": warnings,
    }
