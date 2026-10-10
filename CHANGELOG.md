# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Añadido
- Pestaña **PS5**: explorador de archivos de la consola con el payload de ps5upload
  y descarga de archivos y carpetas completas (progreso, velocidad, cancelación,
  reanudación con `.part` y `REST`, verificación de tamaño y de espacio libre).
- Cliente mínimo del protocolo AVA1 de ps5upload (Noise XX, emparejamiento CPace
  con el código de la consola, `ftp.start`), verificado con sus vectores oficiales.
- El FTP de la PS5 se inicia en solo lectura y con credenciales aleatorias.
- Ajustes persistentes (IP, puerto, carpeta de descargas) y guía `docs/PS5.md`.
- **Comprimir y reemplazar** un juego de la PS5 (carpeta, `.exfat` o `.ffpkg`):
  descarga, ventana de compresión con estimación, compresión con MkPFS, subida
  verificada como `.part`, borrado del original y publicación del `.ffpfsc`.
- **Subir** archivos a la PS5 (con reanudación) y **eliminar** archivos y carpetas
  (con el borrado protegido del helper).
- El FTP solo tiene permiso de escritura mientras dura una operación.
- **Tiempo restante (ETA)** y porcentaje en compresiones, descargas, subidas y en
  "comprimir y reemplazar".
- Ventana de "comprimir y reemplazar" simplificada a 3 pasos: Descarga,
  Compresión y Reemplazo.
- Carpeta `payload/` con el helper de ps5upload 6.4.0 y su guía de carga.
- Reintentos automáticos (hasta 3) ante cortes de conexión en descargas y subidas,
  y reintento manual: "Reintentar fallidas" en el panel de transferencias y
  "Reintentar" en "comprimir y reemplazar" (sin volver a comprimir ni a borrar).
- ETA más estable: velocidad promedio de 30 s y cuenta regresiva entre recálculos.
- Botón **Subir a la PS5** en la pestaña Convertir para los juegos ya comprimidos;
  conecta si hace falta (o explica cómo vincular la PS5) y sube cuando se conecta.

### Corregido
- Tras cancelar "comprimir y reemplazar", el botón "Cerrar" quedaba deshabilitado.
- Una subida reanudada podía mezclar dos archivos distintos si se volvía a
  comprimir con otras opciones; ahora se comparan los últimos bytes antes de reanudar.
- Cancelar una transferencia esperaba al servidor; ahora la conexión se corta al instante.

## [1.1.0] - 2026-10-09

### Añadido
- Rules de Claude Code en `.claude/rules/`: documentación en español neutro,
  límite de 250 líneas por archivo, código limpio y buenas prácticas.
- `tools/check_standards.py`: verifica el límite de líneas y que toda función
  tenga docstring con `Args`, `Returns`, `Yields` y `Raises`; se ejecuta en `pytest`.
- Tests del verificador y de la comprobación de espacio libre.

### Cambiado
- Todas las funciones y métodos documentados con descripción breve, parámetros,
  retorno y excepciones.
- `ui/app.py` dividido en `main_view.py`, `options_panel.py`, `job_table.py`,
  `dialogs.py` y `event_handlers.py`; `app.py` queda como controlador.
- `infrastructure/mkpfs_adapter.py` convertido en subpaquete (`command`,
  `output`, `process`, `metadata`) con la misma API pública.

## [1.0.0] - 2026-10-09

### Añadido
- Paquete `ffpfsc_converter` con arquitectura en capas (`domain`, `infrastructure`,
  `services`, `ui`).
- Suite de tests con pytest (descubrimiento, metadatos, estimación, adaptador
  MkPFS, cola de conversión y textos de la UI).
- Configuración de `ruff`, `pyproject.toml` y comando `ffpfsc-converter`.
- Documentación: README, arquitectura, guía de uso y guía de desarrollo.
- Skills de Claude Code para arquitectura, código limpio y buenas prácticas.
- `instalar.sh --dev` instala también las herramientas de desarrollo.

### Cambiado
- `conversor.py` (archivo único) se reemplaza por el paquete; `abrir.sh` ahora
  ejecuta `python -m ffpfsc_converter` y es portable (no tiene rutas fijas).
- Los eventos entre hilos son dataclasses tipadas en lugar de tuplas.
- El estado del trabajo (`JobState`) se separa del texto mostrado.

### Corregido
- La estimación y el resultado mostraban `−-35%` cuando el archivo crecía;
  ahora se muestra `+35%`.

## [0.1.0] - 2026-10-09

- Primera versión funcional: interfaz Tkinter con arrastrar y soltar,
  estimación de tamaño y conversión con MkPFS.
