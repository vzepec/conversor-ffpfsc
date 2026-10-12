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
#: «Rendimiento en la PS5»: ganancia mínima (en %) para que MkPFS guarde comprimido un
#: bloque de 64 KiB (``--threshold-gain``). Los bloques que casi no se reducen (texturas
#: y audio ya comprimidos por el juego) quedan en crudo: la consola no tiene que
#: descomprimirlos al leer y el archivo pesa apenas un poco más.
PERFORMANCE_THRESHOLD_GAIN = 20

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
#: Intentos (y pausa entre ellos) para volver el FTP a solo lectura tras escribir.
FTP_RESTORE_ATTEMPTS = 3
FTP_RESTORE_RETRY_SECONDS = 2.0
#: Conexión automática a la PS5: espera al abrir la app, intentos y pausa al reconectar.
AUTO_CONNECT_DELAY_MS = 800
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY_MS = 5000
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

# --------------------------------------------------- LZ4 en la PS5 (exfat2ampr)
#: Puerto de la API HTTP de exfat2ampr (convierte juegos a AMPR LZ4 dentro de la PS5).
E2A_HTTP_PORT = 6972
#: Puerto del cargador de ELF de la PS5 (etaHEN, elfldr): ahí se envía exfat2ampr.
ELF_LOADER_PORT = 9021
#: Clave de los ajustes con la ruta del ``exfat2ampr.elf`` que eligió el usuario (no se
#: incluye en la app: se descarga de github.com/ViiNCENZO10/exfat2ampr/releases).
E2A_ELF_PATH_KEY = "e2a_elf_path"
#: Página de descargas de exfat2ampr, para mostrarla cuando falta el ELF.
E2A_RELEASES_URL = "https://github.com/ViiNCENZO10/exfat2ampr/releases"
#: Segundos de espera de cada petición a la API (``/api/sources`` recorre los discos).
E2A_HTTP_TIMEOUT_SECONDS = 20
#: Segundos que se espera a que exfat2ampr responda tras enviarlo al cargador de ELF.
E2A_START_TIMEOUT_SECONDS = 30
#: Cada cuánto se consulta el avance de la conversión.
E2A_POLL_SECONDS = 1.0
#: Fallos de red seguidos al consultar el avance antes de darlo por perdido.
E2A_POLL_MAX_FAILURES = 10
#: Clave de los ajustes donde se guarda el token de emparejamiento por consola.
E2A_TOKENS_KEY = "e2a_tokens"
#: Modos de compresión LZ4: 1-4 rápido, 5-12 HC (más lento al comprimir, igual de rápido
#: al leer); exfat2ampr recomienda HC 9.
LZ4_PRESETS: tuple[CompressionPreset, ...] = (
    CompressionPreset("Rápido (LZ4 1)", "Rápido", 1),
    CompressionPreset("Equilibrado (LZ4 HC 9)", "Equilibrado", 9),
    CompressionPreset("Máximo (LZ4 HC 12, lento)", "Máximo", 12),
)
DEFAULT_LZ4_PRESET = LZ4_PRESETS[1]
