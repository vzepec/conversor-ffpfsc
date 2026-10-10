# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Cambiado
- Interfaz rediseñada: barra lateral con navegación, estado de la PS5 (IP, modo del
  FTP y espacio libre) y selector de tema; tema claro y oscuro que sigue al del
  sistema; botones, tarjetas, campos y barras con esquinas redondeadas; filas por
  juego con ficha, estimación, estado y barra de progreso; escala para pantallas HiDPI.
- Vista PS5 rediseñada: tarjeta de conexión, tarjetas de cada unidad con su espacio
  libre, ruta con tramos clicables y accesos rápidos, lista de archivos con etiquetas
  (Juego, Comprimido, Imagen), barra de acciones según la selección y panel de
  transferencias; contador de transferencias activas en la barra lateral.
- Diálogos de «Comprimir y reemplazar», subida y emparejamiento con el estilo de la app.

### Añadido
- Botón «Subir a la PS5» en cada juego convertido y «Subir completados a la PS5»
  para enviar todos los que aún no están en la consola.
- La subida omite los archivos que ya están en la PS5 con el mismo tamaño.

## [1.2.0] - 2026-10-10

### Añadido
- La versión de la aplicación se muestra en el título de la ventana y a la
  derecha de la línea de estado.
- Soporte **beta** para Windows 10/11: `instalar.bat`/`instalar.ps1` (entorno virtual y
  accesos directos en Escritorio y menú Inicio) y `abrir.bat`.
- Guía de instalación para Linux y Windows (`docs/INSTALLATION.md`).
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
- La pestaña **PS5** muestra el espacio libre del almacenamiento interno, de cada USB
  conectado y del almacenamiento ampliado, y lo actualiza tras borrar, subir o reemplazar.

### Cambiado
- La cancelación termina el árbol de procesos con `taskkill /T` en Windows y
  con `SIGTERM` al grupo en Linux/macOS.
- "Abrir carpeta de salida" usa el Explorador en Windows y `open` en macOS.
- Los diálogos abren en la carpeta Escritorio o Desktop (también en OneDrive).

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
