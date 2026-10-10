"""Configuración central: todas las constantes de la aplicación viven aquí.

Ningún otro módulo debe definir "números mágicos"; si necesitas un valor
ajustable, agrégalo en este archivo con un comentario que explique su origen.
"""
from __future__ import annotations

from ffpfsc_converter.domain.models import CompressionPreset

APP_TITLE = "Conversor FFPFSC (PS5)"

# --------------------------------------------------------------- compresión
#: zlib-ng es el backend seguro para el descompresor de la PS5 (isal genera
#: bloques que la consola lee mal: MkPFS issue #132).
COMPRESSION_BACKEND = "zlib-ng"

PRESETS: tuple[CompressionPreset, ...] = (
    CompressionPreset("Máxima velocidad (nivel 3)", "Máxima velocidad", 3),
    CompressionPreset("Equilibrado (nivel 6)", "Equilibrado", 6),
    CompressionPreset("Máxima compresión (nivel 9, lento)", "Máxima compresión", 9),
)
DEFAULT_PRESET = PRESETS[0]

# -------------------------------------------------------------- estimación
#: Tamaño de bloque PFSC usado por MkPFS (64 KiB).
PFSC_BLOCK_SIZE = 64 * 1024
#: Bloques muestreados al azar por juego (~96 MB leídos).
ESTIMATE_SAMPLE_BLOCKS = 1536
#: Semilla fija: la misma carpeta produce siempre la misma estimación.
ESTIMATE_SEED = 12345
#: Sobrecarga relativa de tablas PFS/exFAT + índices de bloques.
PFS_OVERHEAD_RATIO = 1.003
#: Sobrecarga fija de cabeceras del contenedor.
PFS_OVERHEAD_BYTES = 1024 * 1024
#: Margen sobre la estimación al comprobar espacio libre en destino.
FREE_SPACE_MARGIN = 1.05

# ---------------------------------------------------------------- juegos
#: Extensiones de imagen aceptadas como origen.
IMAGE_EXTENSIONS = frozenset({".exfat", ".ffpkg"})
#: Archivo que identifica la raíz real de un juego.
GAME_ROOT_MARKER = "eboot.bin"
#: Ruta relativa del archivo de metadatos dentro del juego.
PARAM_JSON_RELPATH = "sce_sys/param.json"
#: Tamaño máximo de param.json que se lee desde una imagen .exfat.
PARAM_JSON_MAX_BYTES = 4 << 20
#: Idiomas preferidos para el nombre del juego (después del predeterminado y en-US).
PREFERRED_LANGUAGES = ("es-419", "es-ES")
#: Profundidad máxima al buscar eboot.bin dentro de la carpeta arrastrada.
GAME_ROOT_SEARCH_DEPTH = 3
#: Profundidad máxima al buscar un .exfat/.ffpkg dentro de la carpeta arrastrada.
IMAGE_SEARCH_DEPTH = 2

#: Extensión del archivo generado.
OUTPUT_EXTENSION = ".ffpfsc"
