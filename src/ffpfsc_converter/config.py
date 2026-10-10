"""Configuración central: todas las constantes de la aplicación viven aquí.

Ningún otro módulo debe definir "números mágicos"; si necesitas un valor
ajustable, agrégalo en este archivo con un comentario que explique su origen.
"""
from __future__ import annotations

from ffpfsc_converter.domain.models import CompressionPreset

APP_TITLE = "Conversor FFPFSC (PS5)"
#: Nombre de la clase de la ventana en Linux; Tk lo publica como ``Conversor-ffpfsc``
#: (con mayúscula), que es el ``StartupWMClass`` del acceso directo ``.desktop``.
WINDOW_CLASS = "conversor-ffpfsc"
#: Identificador de la app en Windows: agrupa la ventana con su icono en la barra de tareas.
WINDOWS_APP_ID = "vzepec.ConversorFFPFSC"
#: Repositorio de GitHub donde se publican las versiones.
GITHUB_REPOSITORY = "vzepec/conversor-ffpfsc"
#: Consulta de la última versión publicada (API pública de GitHub, sin credenciales).
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
#: Segundos de espera de la consulta de versión antes de darla por fallida.
UPDATE_CHECK_TIMEOUT_SECONDS = 6

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

# ------------------------------------------------------------- PS5 (FTP)
#: Puerto del servidor FTP del helper de ps5upload (se inicia desde su app,
#: pantalla "FTP Server"). ftpsrv usa 2121.
DEFAULT_FTP_PORT = 2122
#: Segundos de espera de red antes de dar la conexión por perdida.
FTP_TIMEOUT_SECONDS = 15
#: Tamaño de bloque al descargar (1 MiB: menos llamadas, misma memoria).
FTP_BLOCK_SIZE = 1024 * 1024
#: Cada cuánto se publica el progreso de una descarga.
PROGRESS_INTERVAL_SECONDS = 0.25
#: Sufijo de los archivos a medio descargar; permite reanudar.
PARTIAL_SUFFIX = ".part"
#: Bytes ya descargados que se vuelven a pedir al reanudar, para comprobar que el
#: servidor respeta la posición (el FTP de ps5upload acepta REST pero envía desde 0).
RESUME_OVERLAP_BYTES = 64 * 1024
#: Mayor posición que el FTP de ps5upload 6.x sabe retomar con REST: la guarda en
#: un entero de 32 bits con signo y, por encima, envía desde 0 o desde otro lugar.
FTP_MAX_RESUME_OFFSET = 2**31 - 1
#: Bloque de lectura al calcular el CRC32 local (comparación con la PS5).
CRC_CHUNK_BYTES = 8 * 1024 * 1024
#: Cada cuánto se consulta el avance del CRC32 que calcula la PS5.
CRC_POLL_SECONDS = 0.5
#: Tamaño máximo de cada archivo de registro y cuántos anteriores se conservan.
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUPS = 3
#: Carpetas de la PS5 que se ofrecen como accesos rápidos.
PS5_FAVORITE_PATHS = (
    "/data/homebrew", "/mnt/usb0", "/mnt/usb1", "/mnt/ext0", "/mnt/ext1", "/data", "/",
)
#: Carpeta inicial al conectar (la que vigila ShadowMount+).
PS5_START_PATH = "/data/homebrew"
#: Porcentaje de uso a partir del cual la barra de una unidad de la PS5 se pinta en ámbar.
STORAGE_WARN_PERCENT = 85
#: Puerto del helper de ps5upload (protocolo AVA1), usado para iniciar el FTP.
AVA1_PORT = 9120
#: Nombre con el que la app se presenta ante la PS5 al emparejarse.
AVA1_CLIENT_NAME = "Conversor FFPFSC"
#: Segundos que se espera el código de emparejamiento (la PS5 corta a los 60 s).
PAIRING_CODE_TIMEOUT_SECONDS = 55
#: Carpeta (dentro de la de descargas) donde el pipeline deja descargas y .ffpfsc.
PIPELINE_WORK_DIR_NAME = "ffpfsc-temporal"
#: Esperas (s) antes de cada reintento automático tras un corte de conexión.
RETRY_DELAYS_SECONDS = (3.0, 10.0, 20.0)
