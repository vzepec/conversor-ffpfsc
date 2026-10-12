"""Modelos de la compresión LZ4 (formato AMPR) que hace exfat2ampr dentro de la PS5.

exfat2ampr es un payload que convierte un juego de la consola en una carpeta AMPR
con sus recursos comprimidos en LZ4; la app solo le da órdenes por su API HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Lz4Compat(Enum):
    """Si el juego puede usar el formato AMPR (lo decide exfat2ampr leyendo sus ejecutables)."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"
    LATER = "later"  # imagen aún sin montar: se comprueba al empezar


class Lz4JobState(Enum):
    """Estado de la conversión en curso en exfat2ampr."""

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass(frozen=True)
class EngineInfo:
    """Respuesta de ``/api/hello``: el motor responde.

    Attributes:
        version (str): Versión de exfat2ampr (por ejemplo ``"1.45"``).
        paired (bool): ``True`` si el token enviado es válido.
    """

    version: str
    paired: bool


@dataclass(frozen=True)
class Lz4Source:
    """Juego de la PS5 que exfat2ampr puede convertir (de ``/api/sources``).

    Attributes:
        path (str): Carpeta del juego o imagen ``.exfat``/``.ffpkg``.
        kind (str): ``"folder"`` o ``"image"``.
        title_id (str): Por ejemplo ``"PPSA01234"``.
        title (str): Nombre del juego.
        version (str): Versión del juego.
        smp_title (str): Title ID con el que ShadowMountPlus monta la imagen; vacío en carpetas.
    """

    path: str
    kind: str
    title_id: str
    title: str
    version: str
    smp_title: str = ""

    @property
    def is_image(self) -> bool:
        """Indica si el origen es una imagen que ShadowMountPlus debe montar.

        Returns:
            bool: ``True`` para ``.exfat``/``.ffpkg``.
        """
        return self.kind == "image"


@dataclass(frozen=True)
class Lz4Destination:
    """Unidad de la PS5 donde puede quedar el juego convertido (de ``/api/destinations``).

    Attributes:
        base (str): Carpeta de juegos de la unidad, por ejemplo ``"/data/homebrew"``.
        kind (str): ``"internal"``, ``"usb"`` o ``"extended"``.
        index (int): N de ``/mnt/usbN`` o ``/mnt/extN``; ``-1`` en la interna.
        label (str): Nombre en inglés que da exfat2ampr (respaldo).
        total (int): Bytes totales.
        free (int): Bytes libres.
        writable (bool): ``True`` si se puede escribir.
        reason (str): Por qué no se puede escribir (``read_only``, ``no_write``, ``full``).
    """

    base: str
    kind: str
    index: int
    label: str
    total: int
    free: int
    writable: bool
    reason: str = ""


@dataclass(frozen=True)
class Lz4Check:
    """Comprobación previa de exfat2ampr para un juego y un destino (de ``/api/check``).

    Attributes:
        title_id (str): Title ID detectado.
        title (str): Nombre del juego.
        source_bytes (int): Tamaño del juego.
        need_typical (int): Espacio que suele necesitar la conversión.
        need_max (int): Espacio en el peor caso (nada se comprime).
        dest_free (int): Bytes libres en el destino.
        dest_total (int): Bytes totales del destino.
        compatible (Lz4Compat): Si el juego usa ``libSceAmpr``.
        errors (tuple[str, ...]): Códigos que impiden empezar (``not_ampr``, ``game_running``…).
        warnings (tuple[str, ...]): Códigos de aviso (``space_low``, ``already_exists``…).
    """

    title_id: str
    title: str
    source_bytes: int
    need_typical: int
    need_max: int
    dest_free: int
    dest_total: int
    compatible: Lz4Compat
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def is_blocked(self) -> bool:
        """Indica si exfat2ampr rechazaría la conversión.

        Returns:
            bool: ``True`` si hay algún código de error.
        """
        return bool(self.errors)


@dataclass(frozen=True)
class Lz4Plan:
    """Lo necesario para mostrar la ventana de compresión LZ4 de un juego.

    Attributes:
        source (Lz4Source): Juego elegido.
        check (Lz4Check): Comprobación previa contra el destino sugerido.
        destinations (tuple[Lz4Destination, ...]): Unidades de la PS5 (con su espacio).
    """

    source: Lz4Source
    check: Lz4Check
    destinations: tuple[Lz4Destination, ...]


@dataclass(frozen=True)
class Lz4Request:
    """Conversión que se pide a exfat2ampr (``/api/start``).

    Attributes:
        source (Lz4Source): Juego a convertir.
        dest_base (str): Carpeta de juegos de la unidad de destino.
        level (int): Nivel LZ4 (1-4 rápido, 5-12 HC).
        verify (bool): ``True`` para decodificar y comprobar cada bloque al terminar.
        remove_source (bool): ``True`` para borrar el original tras una conversión correcta.
        overwrite (bool): ``True`` para reemplazar una conversión anterior del mismo juego.
    """

    source: Lz4Source
    dest_base: str
    level: int
    verify: bool
    remove_source: bool
    overwrite: bool = False

    @property
    def output_path(self) -> str:
        """Calcula la carpeta que creará exfat2ampr (``<destino>/<TITLE_ID>``).

        Returns:
            str: Ruta remota del juego convertido.
        """
        return f"{self.dest_base.rstrip('/')}/{self.source.title_id}"


@dataclass(frozen=True)
class Lz4Status:
    """Estado de exfat2ampr (de ``/api/state``).

    Attributes:
        state (Lz4JobState): Estado de la conversión.
        phase (str): Fase interna (``scan``, ``pack``, ``verify``…).
        percent (int): Avance total (0-100).
        bytes_done (int): Bytes procesados.
        bytes_total (int): Bytes a procesar.
        speed_bps (float): Velocidad actual en bytes por segundo.
        eta_seconds (int | None): Segundos restantes; ``None`` si aún no se conoce.
        code (str): Motivo estable del resultado o de la pausa (``not_ampr``, ``disk_full``…).
        message (str): Detalle en inglés que da exfat2ampr.
        title_id (str): Juego en curso.
        title (str): Nombre del juego en curso.
        dest (str): Carpeta de salida.
        waiting (bool): ``True`` mientras espera que ShadowMountPlus monte la imagen.
        resumable (bool): ``True`` si quedó un punto de reanudación.
        queue (tuple[str, ...]): Conversiones en cola.
    """

    state: Lz4JobState
    phase: str = ""
    percent: int = 0
    bytes_done: int = 0
    bytes_total: int = 0
    speed_bps: float = 0.0
    eta_seconds: int | None = None
    code: str = ""
    message: str = ""
    title_id: str = ""
    title: str = ""
    dest: str = ""
    waiting: bool = False
    resumable: bool = False
    queue: tuple[str, ...] = ()

    @property
    def is_active(self) -> bool:
        """Indica si la conversión sigue en marcha (o en cola).

        Returns:
            bool: ``True`` si corre o si hay algo en cola.
        """
        return self.state is Lz4JobState.RUNNING or (self.state is Lz4JobState.IDLE
                                                      and bool(self.queue))
