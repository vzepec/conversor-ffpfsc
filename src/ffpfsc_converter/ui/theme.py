"""Colores, fuentes y medidas de la interfaz."""
from __future__ import annotations

WINDOW_SIZE = "1120x620"
WINDOW_MIN_SIZE = (700, 500)
TTK_THEME = "clam"
PADDING = {"padx": 10, "pady": 6}

DROP_ZONE_BG = "#1f2937"
DROP_ZONE_FG = "#e5e7eb"
DROP_ZONE_FONT = ("Sans", 13)

LOG_BG = "#111827"
LOG_FG = "#d1d5db"
LOG_FONT = ("Monospace", 9)

#: Color atenuado de la etiqueta de versión.
VERSION_FG = "#6b7280"

#: Intervalo (ms) con el que la UI vacía la cola de eventos.
EVENT_POLL_MS = 100
