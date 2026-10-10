"""Colores, fuentes y medidas de la interfaz."""
from __future__ import annotations

WINDOW_SIZE = "1120x700"
WINDOW_MIN_SIZE = (700, 500)
TTK_THEME = "clam"
PADDING = {"padx": 10, "pady": 6}

DROP_ZONE_BG = "#1f2937"
DROP_ZONE_FG = "#e5e7eb"
DROP_ZONE_FONT = ("Sans", 13)

LOG_BG = "#111827"
LOG_FG = "#d1d5db"
LOG_FONT = ("Monospace", 9)

#: Intervalo (ms) con el que la UI vacía la cola de eventos.
EVENT_POLL_MS = 100

#: Color atenuado de los textos de ayuda.
HINT_FG = "#6b7280"
#: Color de advertencias (operaciones que borran en la PS5).
WARNING_FG = "#b45309"
#: Color de la etapa en curso del pipeline.
ACCENT_FG = "#1d4ed8"
