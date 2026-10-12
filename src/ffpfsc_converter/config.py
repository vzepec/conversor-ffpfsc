"""Configuración central: todas las constantes de la aplicación viven aquí.

Ningún otro módulo debe definir "números mágicos"; si necesitas un valor
ajustable, agrégalo en este archivo con un comentario que explique su origen.
"""
from __future__ import annotations

from ffpfsc_converter.domain.models import CompressionPreset
from ffpfsc_converter.domain.third_party import ThirdPartyAsset

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
#: Carpeta donde se instalan los juegos en cada unidad de la PS5.
PS5_GAMES_FOLDER = "homebrew"
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

# --------------------------------------------------------------- LZ4 (PC)
#: Sufijo de la carpeta LZ4 que se crea junto a donde iría el ``.ffpfsc``.
LZ4_SEPARATE_NAME_SUFFIX = "-LZ4"

# ------------------------------------------------- archivos de terceros (LZ4)
#: Carpeta (junto a la app, fuera de Git) donde el instalador deja los archivos de terceros.
THIRD_PARTY_DIR_NAME = "third_party"
#: Bloque de lectura al descargar y al calcular el SHA-256.
THIRD_PARTY_CHUNK_BYTES = 1024 * 1024
#: Segundos de espera de red de cada descarga.
THIRD_PARTY_TIMEOUT_SECONDS = 60
_AMPR_RELEASE = "https://github.com/drakmor/ampr_emu/releases/download/0.4.2.1"
#: Lo que descarga el instalador (GPL-3.0; desde su página oficial y con su huella): de
#: ampr_emu, el empaquetador en Python (LZ4 en el PC) y la biblioteca que el juego
#: convertido carga para leer sus paquetes.
THIRD_PARTY_ASSETS: tuple[ThirdPartyAsset, ...] = (
    ThirdPartyAsset(
        "libSceAmpr.sprx (ampr_emu 0.4.2.1)", f"{_AMPR_RELEASE}/libSceAmpr.sprx",
        "69e6c4d5e4f5fb83c9e01815db5861c4c75734acbf4595cafa50d4c218116d1a",
        "ampr_emu/libSceAmpr.sprx"),
    ThirdPartyAsset(
        "herramientas de ampr_emu 0.4.2.1", f"{_AMPR_RELEASE}/ampr-emu-0.4.2.1-fix.zip",
        "9f146f58767f3200a7b619be25d1c32bf3418186e9de4266f81a94d14922d13b",
        "ampr_emu/python-tools", "ampr-pack-tools-windows-x64/python-tools/"),
)
#: Rutas (dentro de ``third_party/``) que usa la app.
AMPR_RUNTIME_FILE = "ampr_emu/libSceAmpr.sprx"
AMPR_TOOLS_DIR = "ampr_emu/python-tools"
#: Scripts de ampr_emu (dentro de ``AMPR_TOOLS_DIR``) y archivos que generan.
AMPR_INDEX_SCRIPT = "build_ampr_index.py"
AMPR_PACK_SCRIPT = "ampr_pack.py"
AMPR_INDEX_FILE = "ampr_emu.index"
AMPR_ASSETS_INDEX = "ampr_assets.index"
#: Carpeta del juego donde va la biblioteca que lee los paquetes LZ4.
AMPR_FAKELIB_DIR = "fakelib"
#: Perfil genérico (sin trazas del juego), con las reglas de exfat2ampr/Lazy_AMPR: queda
#: sin comprimir lo que el juego puede leer sin pasar por libSceAmpr (ejecutables, mmap),
#: lo ya comprimido (vídeo, audio, archivos) y los archivos en la raíz del juego.
AMPR_LOOSE_EXTENSIONS = frozenset({
    ".elf", ".self", ".prx", ".sprx", ".bin", ".dat", ".json", ".xml", ".utoc",
    ".mp4", ".webm", ".mkv", ".bk2", ".bik", ".usm", ".ogg", ".opus", ".mp3", ".at9",
    ".wem", ".zip", ".7z", ".rar", ".crc", ".runtime", ".index", ".pak"})
AMPR_LOOSE_TOP_DIRS = frozenset({
    "sce_module", "sce_sys", "system", "fakelib", "mods", "save", "trophy2", "uds",
    "_duplex_", "decrypted", "movie", "movies", "video", "videos", "cinematic", "cutscene"})
AMPR_LOOSE_NAMES = frozenset({"eboot.bin", "ampr_emu.index", "ampr_commands.bin", "apr_emu.log"})
AMPR_LOOSE_PREFIXES = ("movie", "soundbank", "wem")
#: Carpetas de audio: se leen en trozos pequeños y al azar (bloques de 16 KiB).
AMPR_AUDIO_TOP_DIRS = frozenset({"audio", "sound", "sounds", "sfx", "music", "voice", "voices",
                                 "vo"})
#: Niveles LZ4 hasta este valor usan el modo rápido; desde el siguiente, HC.
LZ4_FAST_MAX_LEVEL = 4
#: Carpetas temporales de la conversión LZ4 en el PC (dentro de la carpeta de destino).
LZ4_WORK_SUFFIX = ".lz4-temporal"
#: Fase de la verificación LZ4 (distinta de la de MkPFS: solo esta se puede saltar).
LZ4_VERIFY_PHASE = "verify-lz4"
LZ4_PARTIAL_SUFFIX = ".parcial"
LZ4_BACKUP_SUFFIX = ".anterior"
#: Estimación del peso LZ4: bloques de 64 KiB muestreados (~32 MB), comprimidos con cada nivel.
LZ4_ESTIMATE_SAMPLE_BLOCKS = 512
#: Nivel LZ4 de cada modo de la vista Convertir (nivel zlib → LZ4): rápido, HC 9 y HC 12.
LZ4_LEVEL_BY_PRESET = {3: 1, 6: 9, 9: 12}
#: Si durante el empaquetado LZ4 el disco de destino baja de esto, se detiene y limpia.
LZ4_MIN_FREE_BYTES = 2 * 1024**3
#: Reglas de ampr_pack para bloques de lectura mixta (para estimar el peso real): un bloque
#: va comprimido solo si ahorra ≥ 8 KiB y ≥ 12,5 %; los comprimidos se alinean a 64 B y no
#: cruzan el borde de una página de 64 KiB (los crudos ocupan una página entera).
AMPR_IO_PAGE_BYTES = 64 * 1024
AMPR_CHUNK_ALIGN_BYTES = 64
AMPR_MIN_SAVINGS_BYTES = 8 * 1024
AMPR_MIN_SAVINGS_RATIO = 0.125
