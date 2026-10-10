"""Estimación del tiempo restante (ETA), compartida por todas las capas (sin dependencias).

El ETA se calcula con la **velocidad promedio de una ventana de tiempo** (los
últimos ``WINDOW_SECONDS``), así un pico o una caída breve no lo mueve. Además,
el valor mostrado **cuenta hacia atrás** como un reloj y solo se corrige cada
``REFRESH_SECONDS`` o si la estimación nueva difiere más de ``TOLERANCE``: con
una conexión inestable el número se mantiene estable.
"""
from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

#: Peso de la muestra nueva en la media móvil de la velocidad mostrada (0-1).
SMOOTHING = 0.3
#: Ventana (s) sobre la que se promedia la velocidad para el ETA.
WINDOW_SECONDS = 30.0
#: Segundos mínimos de medición antes de informar un ETA.
WARMUP_SECONDS = 5.0
#: Cada cuánto (s) se corrige el ETA mostrado como máximo.
REFRESH_SECONDS = 10.0
#: Diferencia relativa que fuerza a corregir el ETA antes de tiempo.
TOLERANCE = 0.25


class SpeedAverage:
    """Media móvil exponencial de una velocidad (para mostrar MB/s sin saltos)."""

    def __init__(self, smoothing: float = SMOOTHING) -> None:
        """Crea la media vacía.

        Args:
            smoothing (float): Peso de cada muestra nueva (0-1).
        """
        self._smoothing = smoothing
        self.value: float | None = None

    def add(self, speed: float) -> float:
        """Incorpora una muestra de velocidad.

        Args:
            speed (float): Velocidad medida (unidades por segundo).

        Returns:
            float: Velocidad suavizada.
        """
        self.value = speed if self.value is None else (
            self.value * (1 - self._smoothing) + speed * self._smoothing)
        return self.value


class EtaEstimator:
    """ETA estable a partir del avance acumulado de una tarea."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Crea el estimador sin muestras.

        Args:
            clock (Callable[[], float]): Reloj monotónico; los tests lo sustituyen.
        """
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        """Descarta las muestras (por ejemplo, al empezar una fase nueva)."""
        self._samples: deque[tuple[float, float]] = deque()
        self._started = self._clock()
        self._shown: float | None = None
        self._shown_at = 0.0

    def update(self, transferred: float, remaining: float) -> float | None:
        """Registra el avance y devuelve el tiempo restante a mostrar.

        Args:
            transferred (float): Cantidad realmente procesada en esta sesión (sin
                contar lo que ya estaba hecho, para no inflar la velocidad).
            remaining (float): Cantidad que falta.

        Returns:
            float | None: Segundos restantes, o ``None`` mientras no haya datos suficientes
            o si el total aún se desconoce.
        """
        now = self._clock()
        self._samples.append((now, transferred))
        while len(self._samples) > 2 and now - self._samples[1][0] >= WINDOW_SECONDS:
            self._samples.popleft()
        if remaining < 0:  # total aún desconocido
            return None
        if remaining == 0:
            return 0.0
        if now - self._started < WARMUP_SECONDS:
            return None
        estimate = remaining_seconds(remaining, self._window_rate())
        return self._stabilize(estimate, now)

    def _window_rate(self) -> float | None:
        """Calcula la velocidad promedio dentro de la ventana.

        Returns:
            float | None: Unidades por segundo, o ``None`` si no hay avance medible.
        """
        (first_time, first_done), (last_time, last_done) = self._samples[0], self._samples[-1]
        elapsed = last_time - first_time
        return (last_done - first_done) / elapsed if elapsed > 0 else None

    def _stabilize(self, estimate: float | None, now: float) -> float | None:
        """Decide si mostrar la estimación nueva o seguir la cuenta regresiva.

        Args:
            estimate (float | None): Estimación recién calculada.
            now (float): Instante actual.

        Returns:
            float | None: ETA a mostrar.
        """
        if estimate is None:
            return self._countdown(now)
        current = self._countdown(now)
        stale = now - self._shown_at >= REFRESH_SECONDS
        far = current is None or abs(estimate - current) > TOLERANCE * max(current, 1.0)
        if stale or far:
            self._shown, self._shown_at = estimate, now
            return estimate
        return current

    def _countdown(self, now: float) -> float | None:
        """Calcula el ETA mostrado descontando el tiempo transcurrido.

        Args:
            now (float): Instante actual.

        Returns:
            float | None: ETA mostrado actualizado, o ``None`` si aún no hay.
        """
        if self._shown is None:
            return None
        return max(self._shown - (now - self._shown_at), 0.0)


def remaining_seconds(remaining: float, speed: float | None) -> float | None:
    """Calcula el tiempo restante a una velocidad dada.

    Args:
        remaining (float): Cantidad que falta (bytes, porcentaje…).
        speed (float | None): Velocidad en las mismas unidades por segundo.

    Returns:
        float | None: Segundos restantes, o ``None`` si la velocidad no es positiva.
    """
    if not speed or speed <= 0 or remaining < 0:
        return None
    return remaining / speed


class PercentEta:
    """ETA para avances en porcentaje por fase (MkPFS): reinicia al cambiar de fase."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Crea el estimador.

        Args:
            clock (Callable[[], float]): Reloj monotónico; los tests lo sustituyen.
        """
        self._phase: str | None = None
        self._last_percent = 0.0
        self._estimator = EtaEstimator(clock)

    def update(self, phase: str, percent: float) -> float | None:
        """Registra un avance y estima lo que falta de la fase actual.

        Args:
            phase (str): Nombre de la fase.
            percent (float): Porcentaje completado de la fase (0-100).

        Returns:
            float | None: Segundos restantes de la fase, o ``None`` si aún no se sabe.
        """
        if phase != self._phase or percent < self._last_percent:
            self._phase = phase
            self._estimator.reset()
        self._last_percent = percent
        return self._estimator.update(percent, 100 - percent)
