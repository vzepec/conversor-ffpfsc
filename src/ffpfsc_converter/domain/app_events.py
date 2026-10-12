"""Unión de los eventos que recibe la ventana principal y el tipo de su receptor.

La cola de la ventana recibe eventos de la conversión, de la PS5 y de la
compresión LZ4. Como ``Callable`` es contravariante en su argumento, un
:data:`AppEventSink` sirve donde se espera un ``EventSink`` o un ``Lz4Sink``.
"""
from __future__ import annotations

from collections.abc import Callable

from ffpfsc_converter.domain.events import Event
from ffpfsc_converter.domain.lz4_events import Lz4Event
from ffpfsc_converter.domain.remote_events import RemoteEvent

AppEvent = Event | RemoteEvent | Lz4Event

#: Recibe cualquier evento de la app; debe poder llamarse desde cualquier hilo.
AppEventSink = Callable[[AppEvent], None]
