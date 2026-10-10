"""Escritura de un ``.part`` que verifica la reanudación y nunca supera el tamaño esperado.

Al reanudar se pide a la PS5 un tramo que se solapa con lo que ya está en
disco. Si coincide, se continúa; si lo recibido es el comienzo del archivo (el
servidor ignoró ``REST``), se reescribe desde cero sin cortar la conexión; si no
coincide con nada, el ``.part`` está dañado y se descarta.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import TracebackType

from ffpfsc_converter.errors import ConverterError, TransientError


class ResumeMismatchError(TransientError):
    """La parte descargada no coincide con el archivo de la PS5."""

    def __init__(self, path: Path) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            path (Path): Archivo a medio descargar que se descarta.
        """
        super().__init__(f"La descarga a medias de {path.name} no coincidía con la PS5; "
                         "se descargará de nuevo desde el principio.")


class OversizeDownloadError(ConverterError):
    """La PS5 envió más datos que el tamaño que informó del archivo."""

    def __init__(self, path: Path, expected: int) -> None:
        """Crea el error con un mensaje para el usuario.

        Args:
            path (Path): Archivo que se estaba descargando.
            expected (int): Tamaño informado por la PS5.
        """
        super().__init__(f"La PS5 envió más datos de los esperados para {path.name} "
                         f"({expected} bytes). Se canceló para no llenar el disco.")


class LocalOSError(Exception):
    """Envoltorio para distinguir errores del disco local de los de red.

    Attributes:
        original (OSError): Error del sistema al escribir.
    """

    def __init__(self, original: OSError) -> None:
        """Guarda el error original.

        Args:
            original (OSError): Error del sistema al escribir.
        """
        super().__init__(str(original))
        self.original = original


class ResumingWriter:
    """Destino de la descarga de un archivo (se usa como ``with``)."""

    def __init__(self, part: Path, size: int, offset: int, overlap: int,
                 progress: tuple[Callable[[int], None], Callable[[int], None]]) -> None:
        """Abre el ``.part`` listo para continuar.

        Args:
            part (Path): Archivo temporal.
            size (int): Tamaño final esperado.
            offset (int): Bytes que ya hay en el ``.part``.
            overlap (int): Bytes previos a ``offset`` que la PS5 volverá a enviar.
            progress (tuple[Callable[[int], None], Callable[[int], None]]): Funciones que
                suman bytes nuevos al avance y que descuentan los que se descartan.

        Raises:
            OSError: Si no se pudo abrir el archivo local.
        """
        self._part, self._size = part, size
        self._file = part.open("r+b" if offset else "wb")
        self._file.seek(offset)
        self._position, self._pending = offset, overlap
        self._buffer = bytearray()
        self._advance, self._rewind = progress

    def __enter__(self) -> ResumingWriter:
        """Devuelve el propio escritor.

        Returns:
            ResumingWriter: Escritor abierto.
        """
        return self

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None,
                 trace: TracebackType | None) -> None:
        """Cierra el archivo; si el ``.part`` no sirve, lo borra.

        Args:
            kind (type[BaseException] | None): Tipo de la excepción, si hubo.
            error (BaseException | None): Excepción, si hubo.
            trace (TracebackType | None): Traza, si hubo.
        """
        self._file.close()
        if isinstance(error, (ResumeMismatchError, OversizeDownloadError)):
            self._part.unlink(missing_ok=True)

    def write(self, data: bytes) -> int:
        """Recibe un bloque: primero verifica el solapamiento y luego lo agrega.

        Args:
            data (bytes): Datos recibidos de la PS5.

        Returns:
            int: Bytes recibidos.

        Raises:
            ResumeMismatchError: Si el solapamiento no coincide con el ``.part``.
            OversizeDownloadError: Si se superaría el tamaño esperado.
            LocalOSError: Si el disco local rechaza la escritura.
        """
        if not self._pending:
            self._append(data)
            return len(data)
        self._buffer += data
        if len(self._buffer) >= self._pending:
            self._append(self._resolve())
        return len(data)

    def finish(self) -> None:
        """Comprueba que la PS5 llegó a enviar el solapamiento completo.

        Raises:
            ResumeMismatchError: Si la transferencia terminó antes de poder verificarla.
        """
        if self._pending:
            raise ResumeMismatchError(self._part)

    def _resolve(self) -> bytes:
        """Decide si continuar o reescribir según el solapamiento recibido.

        Returns:
            bytes: Datos a escribir a partir de la posición resultante.

        Raises:
            ResumeMismatchError: Si lo recibido no es ni la continuación ni el comienzo.
            LocalOSError: Si no se pudo leer o recortar el ``.part``.
        """
        received, overlap = bytes(self._buffer), self._pending
        self._pending, self._buffer = 0, bytearray()
        if received[:overlap] == self._read(self._position - overlap, overlap):
            return received[overlap:]
        if received[:overlap] == self._read(0, overlap):
            self._rewind(self._position)
            self._position = 0
            try:
                self._file.seek(0)
                self._file.truncate()
            except OSError as exc:
                raise LocalOSError(exc) from exc
            return received
        raise ResumeMismatchError(self._part)

    def _read(self, start: int, length: int) -> bytes:
        """Lee un tramo del ``.part`` y deja el cursor al final de lo escrito.

        Args:
            start (int): Posición inicial.
            length (int): Bytes a leer.

        Returns:
            bytes: Datos leídos.

        Raises:
            LocalOSError: Si no se pudo leer.
        """
        try:
            self._file.seek(start)
            data = self._file.read(length)
            self._file.seek(self._position)
        except OSError as exc:
            raise LocalOSError(exc) from exc
        return data

    def _append(self, data: bytes) -> None:
        """Escribe datos al final sin pasar del tamaño esperado.

        Args:
            data (bytes): Datos nuevos.

        Raises:
            OversizeDownloadError: Si se superaría el tamaño esperado.
            LocalOSError: Si el disco local rechaza la escritura.
        """
        if self._position + len(data) > self._size:
            raise OversizeDownloadError(self._part, self._size)
        try:
            self._file.write(data)
        except OSError as exc:
            raise LocalOSError(exc) from exc
        self._position += len(data)
        if data:
            self._advance(len(data))
