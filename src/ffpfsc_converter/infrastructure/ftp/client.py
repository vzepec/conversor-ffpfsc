"""Sesión FTP con la PS5 sobre ``ftplib`` (biblioteca estándar).

Particularidades del servidor del helper de ps5upload que este cliente respeta:

- ``MLSD`` ignora la ruta que recibe y lista la carpeta actual, así que
  siempre se hace ``CWD`` antes de listar.
- El listado incluye ``.`` y ``..``; se filtran en ``listing.py``.
- Una sesión ``ftplib`` no es segura entre hilos: cada servicio usa la suya.
"""
from __future__ import annotations

import ftplib
from collections.abc import Callable, Iterator
from typing import BinaryIO

from ffpfsc_converter.config import FTP_BLOCK_SIZE, FTP_TIMEOUT_SECONDS
from ffpfsc_converter.domain.remote import ConsoleTarget, RemoteEntry
from ffpfsc_converter.infrastructure.ftp.listing import (
    entries_from_mlsd,
    parse_list_line,
    sort_entries,
)

_ANONYMOUS_USER = "anonymous"
_ANONYMOUS_PASSWORD = "anonymous@"


class FtpClient:
    """Conexión FTP con una PS5, con las operaciones que necesita la app."""

    def __init__(self, target: ConsoleTarget, timeout: float = FTP_TIMEOUT_SECONDS) -> None:
        """Prepara el cliente sin conectarse todavía.

        Args:
            target (ConsoleTarget): Consola a la que se conectará.
            timeout (float): Segundos de espera de red por operación.
        """
        self.target = target
        self._timeout = timeout
        self._ftp: ftplib.FTP | None = None
        self._interrupted = False

    def connect(self) -> None:
        """Abre la conexión, inicia sesión y activa el modo binario pasivo.

        Raises:
            OSError: Si la PS5 no responde o rechaza la conexión.
            ftplib.Error: Si el servidor rechaza el inicio de sesión.
        """
        ftp = ftplib.FTP(timeout=self._timeout)
        ftp.connect(self.target.host, self.target.port)
        ftp.login(self.target.user or _ANONYMOUS_USER,
                  self.target.password or _ANONYMOUS_PASSWORD)
        ftp.set_pasv(True)
        ftp.voidcmd("TYPE I")
        self._ftp = ftp

    def close(self) -> None:
        """Cierra la conexión; si una transferencia se interrumpió, la corta sin esperar."""
        ftp, self._ftp = self._ftp, None
        if ftp is None:
            return
        if self._interrupted:  # el servidor aún puede estar enviando: QUIT esperaría
            ftp.close()
            return
        try:
            ftp.quit()
        except (OSError, EOFError, ftplib.Error):
            ftp.close()

    @property
    def is_connected(self) -> bool:
        """Indica si hay una sesión abierta.

        Returns:
            bool: ``True`` entre ``connect`` y ``close``.
        """
        return self._ftp is not None

    def list_dir(self, path: str) -> list[RemoteEntry]:
        """Lista una carpeta de la PS5.

        Usa ``MLSD`` y, si el servidor no lo soporta, ``LIST``.

        Args:
            path (str): Carpeta remota absoluta.

        Returns:
            list[RemoteEntry]: Contenido ordenado (carpetas primero).

        Raises:
            ftplib.error_perm: Si la carpeta no existe o no se puede abrir.
            OSError: Si se pierde la conexión.
        """
        ftp = self._session()
        ftp.cwd(path)
        try:
            entries = entries_from_mlsd(path, ftp.mlsd())
        except ftplib.error_perm:
            lines: list[str] = []
            ftp.retrlines("LIST", lines.append)
            entries = [e for line in lines if (e := parse_list_line(path, line))]
        return sort_entries(entries)

    def walk(self, path: str) -> Iterator[RemoteEntry]:
        """Recorre una carpeta remota y todas sus subcarpetas.

        Args:
            path (str): Carpeta remota absoluta.

        Yields:
            RemoteEntry: Cada carpeta antes que su contenido, y cada archivo.
        """
        for entry in self.list_dir(path):
            yield entry
            if entry.is_dir:
                yield from self.walk(entry.path)

    def download(
        self,
        remote_path: str,
        sink: BinaryIO,
        offset: int,
        on_chunk: Callable[[int], None],
    ) -> None:
        """Descarga un archivo, opcionalmente desde un desplazamiento (``REST``).

        Args:
            remote_path (str): Archivo remoto absoluto.
            sink (BinaryIO): Destino abierto en modo binario, ya posicionado en ``offset``.
            offset (int): Bytes ya descargados; ``0`` para empezar desde el principio.
            on_chunk (Callable[[int], None]): Se llama con el tamaño de cada bloque
                recibido; puede lanzar una excepción para abortar la descarga.

        Raises:
            ftplib.Error: Si el servidor rechaza la descarga.
            OSError: Si se pierde la conexión o falla la escritura local.
        """
        def write(block: bytes) -> None:
            """Escribe un bloque recibido y notifica su tamaño.

            Args:
                block (bytes): Datos recibidos del servidor.
            """
            sink.write(block)
            on_chunk(len(block))

        try:
            self._session().retrbinary(f"RETR {remote_path}", write,
                                       blocksize=FTP_BLOCK_SIZE, rest=offset or None)
        except BaseException:
            self._interrupted = True
            raise

    def upload(
        self, source: BinaryIO, remote_path: str, offset: int, on_chunk: Callable[[int], None]
    ) -> None:
        """Sube un archivo, opcionalmente continuando desde un desplazamiento (``REST``).

        Args:
            source (BinaryIO): Archivo local abierto en binario, posicionado en ``offset``.
            remote_path (str): Ruta remota de destino.
            offset (int): Bytes que ya están en la PS5; ``0`` para empezar de cero.
            on_chunk (Callable[[int], None]): Se llama con el tamaño de cada bloque enviado;
                puede lanzar una excepción para abortar.

        Raises:
            ftplib.Error: Si el servidor rechaza la escritura (por ejemplo, en solo lectura).
            OSError: Si se pierde la conexión.
        """
        try:
            self._session().storbinary(f"STOR {remote_path}", source, blocksize=FTP_BLOCK_SIZE,
                                       callback=lambda block: on_chunk(len(block)),
                                       rest=offset or None)
        except BaseException:
            self._interrupted = True
            raise

    def size(self, remote_path: str) -> int | None:
        """Consulta el tamaño de un archivo remoto.

        Args:
            remote_path (str): Ruta remota.

        Returns:
            int | None: Tamaño en bytes, o ``None`` si el archivo no existe.

        Raises:
            OSError: Si se pierde la conexión.
        """
        try:
            return self._session().size(remote_path)
        except ftplib.error_perm:
            return None

    def rename(self, source: str, destination: str) -> None:
        """Renombra un archivo remoto (siempre dentro del mismo disco).

        Args:
            source (str): Ruta actual.
            destination (str): Ruta nueva.

        Raises:
            ftplib.Error: Si el servidor lo rechaza (el de ps5upload rechaza cruzar discos).
            OSError: Si se pierde la conexión.
        """
        self._session().rename(source, destination)

    def make_dir(self, remote_path: str) -> None:
        """Crea una carpeta remota; si ya existe, no hace nada.

        Args:
            remote_path (str): Ruta de la carpeta (su carpeta padre debe existir).

        Raises:
            ftplib.Error: Si no se puede crear y tampoco existe.
            OSError: Si se pierde la conexión.
        """
        session = self._session()
        try:
            session.mkd(remote_path)
        except ftplib.error_perm:
            session.cwd(remote_path)  # ya existía: entrar confirma que es una carpeta
            session.cwd("/")

    def _session(self) -> ftplib.FTP:
        """Obtiene la sesión abierta.

        Returns:
            ftplib.FTP: Sesión activa.

        Raises:
            ConnectionError: Si no se llamó antes a ``connect``.
        """
        if self._ftp is None:
            raise ConnectionError("No hay conexión con la PS5")
        return self._ftp
