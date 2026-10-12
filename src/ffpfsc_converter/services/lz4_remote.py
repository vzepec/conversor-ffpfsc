"""Compresión LZ4 de juegos dentro de la PS5 con exfat2ampr, sin bloquear la interfaz.

Cada orden corre en un hilo daemon y publica eventos de
:mod:`ffpfsc_converter.domain.lz4_events`. La conversión la hace la consola; la
app solo la pide, la sigue y la controla por la API HTTP del motor.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from http import HTTPStatus

from ffpfsc_converter.domain.lz4 import Lz4Request
from ffpfsc_converter.domain.lz4_events import Lz4Failed, Lz4PairingRequired
from ffpfsc_converter.errors import ConverterError
from ffpfsc_converter.infrastructure.exfat2ampr import E2aHttpError
from ffpfsc_converter.services.lz4_deps import Lz4Deps, Lz4Sink
from ffpfsc_converter.services.lz4_flows import Lz4Flows
from ffpfsc_converter.services.lz4_messages import engine_error_text, network_error_text
from ffpfsc_converter.services.lz4_tracking import FollowerRegistry

_Task = Callable[[], None]


class Lz4Remote:
    """Prepara, inicia, sigue y controla conversiones LZ4 de exfat2ampr."""

    def __init__(self, emit: Lz4Sink, deps: Lz4Deps | None = None) -> None:
        """Prepara el servicio sin conectarse a ninguna consola.

        Args:
            emit (Lz4Sink): Destino de los eventos (seguro entre hilos).
            deps (Lz4Deps | None): Dependencias; ``None`` usa las reales.
        """
        self._emit = emit
        self._deps = deps or Lz4Deps()
        self._followers = FollowerRegistry(self._deps, emit)
        self._flows = Lz4Flows(self._deps, emit, self._followers)

    @property
    def busy(self) -> bool:
        """Indica si hay una conversión iniciándose o en seguimiento.

        Returns:
            bool: ``True`` mientras se inicia, reanuda o sigue una conversión.
        """
        return self._followers.busy

    def prepare(self, host: str, entry_path: str) -> threading.Thread:
        """Asegura que exfat2ampr responde y analiza el juego elegido.

        Publica ``Lz4Ready``, o lo que falte antes: ``Lz4ElfRequired``,
        ``Lz4EngineLaunched``, ``Lz4PairingRequired`` o ``Lz4Failed``.

        Args:
            host (str): Dirección de la PS5.
            entry_path (str): Carpeta o imagen elegida en la PS5.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        return self._spawn(lambda: self._flows.prepare(host, entry_path), host, entry_path)

    def pair(self, host: str, pin: str, entry_path: str) -> threading.Thread:
        """Empareja la app con el código de la PS5 y continúa con el análisis.

        Args:
            host (str): Dirección de la PS5.
            pin (str): Código de 6 dígitos de la notificación de exfat2ampr.
            entry_path (str): Juego que se quería convertir.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        return self._spawn(lambda: self._flows.pair(host, pin, entry_path), host, entry_path)

    def start(self, host: str, request: Lz4Request) -> threading.Thread:
        """Comprueba el destino elegido, pide la conversión y la sigue.

        Publica ``Lz4Rejected`` si la comprobación final falla; si no,
        ``Lz4Started``, ``Lz4Progress`` y ``Lz4Finished``.

        Args:
            host (str): Dirección de la PS5.
            request (Lz4Request): Conversión a pedir.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        task = self._followers.tracked(lambda: self._flows.start(host, request))
        return self._spawn(task, host, request.source.path)

    def pause(self, host: str) -> threading.Thread:
        """Pausa la conversión dejando un punto de reanudación.

        Args:
            host (str): Dirección de la PS5.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        return self._spawn(lambda: self._deps.client(host).pause(), host, "")

    def resume(self, host: str, dest: str) -> threading.Thread:
        """Reanuda una conversión en pausa y vuelve a seguirla.

        Args:
            host (str): Dirección de la PS5.
            dest (str): Carpeta de salida de la conversión en pausa.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        task = self._followers.tracked(lambda: self._flows.resume(host, dest))
        return self._spawn(task, host, "")

    def cancel(self, host: str) -> threading.Thread:
        """Cancela la conversión (exfat2ampr borra su salida parcial).

        Args:
            host (str): Dirección de la PS5.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        return self._spawn(lambda: self._deps.client(host).cancel(), host, "")

    def watch(self, host: str) -> threading.Thread:
        """Sigue la conversión que exfat2ampr ya tenga en marcha al conectarse.

        Si el motor no responde, no hay token o no hay nada en marcha, no publica nada.

        Args:
            host (str): Dirección de la PS5.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        return self._spawn(lambda: self._flows.watch(host), host, "")

    def stop_watching(self) -> None:
        """Deja de seguir las conversiones (siguen en la PS5)."""
        self._followers.stop_all()

    def _spawn(self, task: _Task, host: str, entry_path: str) -> threading.Thread:
        """Ejecuta una tarea en un hilo daemon convirtiendo sus errores en eventos.

        Args:
            task (_Task): Trabajo a ejecutar.
            host (str): Dirección de la PS5 (para los eventos de error).
            entry_path (str): Juego en curso, para volver a pedir el emparejamiento.

        Returns:
            threading.Thread: Hilo ya iniciado.
        """
        thread = threading.Thread(target=self._run_guarded, args=(task, host, entry_path),
                                  daemon=True)
        thread.start()
        return thread

    def _run_guarded(self, task: _Task, host: str, entry_path: str) -> None:
        """Ejecuta la tarea y publica ``Lz4Failed`` o ``Lz4PairingRequired`` si falla.

        Args:
            task (_Task): Trabajo a ejecutar.
            host (str): Dirección de la PS5.
            entry_path (str): Juego en curso (vacío si la orden no es de un juego).
        """
        try:
            task()
        except E2aHttpError as exc:
            if exc.status == HTTPStatus.UNAUTHORIZED:
                self._deps.settings.forget_token(host)
                self._emit(Lz4PairingRequired(host, entry_path))
                return
            self._emit(Lz4Failed(host, engine_error_text(exc.code or exc.error, exc.error)))
        except OSError:
            self._emit(Lz4Failed(host, network_error_text(host)))
        except ConverterError as exc:
            self._emit(Lz4Failed(host, str(exc)))
