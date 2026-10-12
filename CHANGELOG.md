# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Cambiado
- README reescrito para usuarios no técnicos: qué hace, qué necesitas, instalación,
  uso paso a paso, `.ffpfsc` o LZ4 (experimental) y preguntas frecuentes. Lo técnico
  (tecnologías, componentes, arquitectura y desarrollo) pasa a
  [docs/TECHNICAL.md](docs/TECHNICAL.md).

### Añadido (experimental)
- **Comprimir LZ4 en la PS5…** (sección PS5): convierte el juego seleccionado al
  formato AMPR LZ4 dentro de la consola con
  [exfat2ampr](https://github.com/ViiNCENZO10/exfat2ampr) 1.45, que no viene incluido:
  la app pide el `exfat2ampr.elf` una vez y lo envía al cargador de ELF (9021) cuando
  hace falta, se empareja con el código de la notificación y muestra el avance en
  Transferencias con Cancelar y Reanudar. Si abres en la PS5 el juego que se
  convierte, la fila indica que se reanudará sola al cerrarlo. Textos cortos y sin
  jerga; el detalle técnico queda en Registros. Su autor no lo probó en consola:
  conserva el original hasta probar el juego. Guía: [docs/LZ4.md](docs/LZ4.md).
- **Formato LZ4 en la vista Convertir** (en este equipo): selector «Formato»; la cola
  indica si cada juego es compatible y su peso estimado en LZ4, y la conversión usa
  las herramientas de [ampr_emu](https://github.com/drakmor/ampr_emu) 0.4.2.1
  (perfil genérico, verificación byte a byte contra el original) y deja una carpeta
  `<juego>-LZ4`. Solo carpetas de juego; el original nunca se modifica.
- **Subir carpetas a la PS5**: «Subir a la PS5… → Carpeta…» en la sección PS5 y «Subir a
  la PS5» para los juegos convertidos a LZ4 en Convertir. La carpeta va primero a
  `<nombre>.part/` (cada archivo verificado, con reintentos y reanudación) y se publica
  con su nombre al final; nunca sobrescribe una carpeta existente.
- Los instaladores descargan `exfat2ampr.elf` y lo necesario de ampr_emu en
  `third_party/` (fuera de Git) desde sus páginas oficiales, con su SHA-256
  comprobado. Sin internet avisan y siguen. Nueva dependencia: `lz4`.

## [1.6.0] - 2026-10-11

### Añadido
- Opción **Rendimiento en la PS5** (vista Convertir y «Comprimir y reemplazar»):
  MkPFS solo guarda comprimidos los bloques que se reducen al menos un 20 %
  (`--threshold-gain 20`); el resto queda en crudo y la consola no tiene que
  descomprimirlo al cargar. El `.ffpfsc` pesa algo más y el peso estimado de la
  cola lo muestra. Pensada para juegos grandes; la app la recuerda entre sesiones.

### Cambiado
- Las opciones de Convertir pasan a una segunda línea cuando la ventana es angosta,
  en vez de quedar cortadas.

## [1.5.0] - 2026-10-10

### Añadido
- Arrastrar (o elegir) un `.ffpfsc` ya comprimido en la vista Convertir lo agrega a
  la cola como «✓ Ya comprimido», con su nombre, Title ID y versión leídos del
  archivo, y el botón «Subir a la PS5» listo; no se vuelve a comprimir y también
  entra en «Subir completados a la PS5».

### Corregido
- Tras subir a la PS5 (por ejemplo, desde «Subir a la PS5» en Convertir) la vista
  PS5 podía quedar con todos los botones bloqueados, incluso «Desconectar»: si el
  FTP no lograba volver a solo lectura (habitual tras un corte de conexión), el
  error se ignoraba en silencio. Ahora se reintenta, queda en el registro y, si
  aun así falla, la vista reinicia el FTP y se reconecta sola en la misma carpeta.

## [1.4.1] - 2026-10-10

### Corregido
- La app se congelaba al comprimir (sobre todo en Windows y con muchos núcleos):
  MkPFS redibuja su barra cientos o miles de veces por segundo y cada redibujo
  llegaba a la interfaz. Ahora el avance se publica como máximo 4 veces por
  segundo (también en «Comprimir y reemplazar», incluida la comprobación CRC32) y
  la interfaz nunca dedica más de 40 ms seguidos a procesar eventos.
- Volver a convertir un juego cuyo `.ffpfsc` ya existía fallaba con `EOFError`:
  MkPFS preguntaba por consola si sobrescribir. Tras confirmar en la app, el
  archivo anterior se borra antes de lanzar MkPFS.
- Si la app se cerraba a la fuerza, MkPFS seguía comprimiendo en segundo plano.
  Ahora termina junto con la app (Windows: *Job Object*; Linux: `PR_SET_PDEATHSIG`).

## [1.4.0] - 2026-10-10

### Añadido
- «Comprimir y reemplazar» compara con CRC32 lo descargado y lo subido con lo que
  hay en la PS5 (la consola lo calcula con el helper, en paralelo) antes de
  comprimir y antes de borrar el original. Antes solo se comparaba el tamaño.
- El equipo no se suspende mientras haya una conversión o una transferencia con la
  PS5 en curso (Linux: `systemd-inhibit`; Windows: `SetThreadExecutionState`).
- Aviso del escritorio al terminar la cola de conversión, las descargas, una subida
  o «Comprimir y reemplazar», si la ventana no está en primer plano.
- Registro en archivo (`conversor.log`, rotativo) con la salida de MkPFS, los
  eventos de la PS5 y cualquier error inesperado con su traza; el enlace
  «Registros» de la barra lateral abre su carpeta.
- Conexión automática a la PS5 al abrir la app (si ya está vinculada y responde,
  sin mostrar errores si está apagada) y reconexión automática tras un corte,
  hasta 3 intentos, volviendo a la carpeta abierta.
- La app recuerda entre sesiones el modo, los núcleos, la verificación, la carpeta de
  destino (con un enlace para volver a «junto a cada juego»), el tamaño de la
  ventana y la última vista abierta.

### Cambiado
- «Comprimir y reemplazar» ya no abre una ventana de progreso: se sigue en una fila
  del panel de Transferencias con el paso, la barra, el tiempo restante y los
  botones Cancelar o Reintentar. El panel crece según sus filas.
- Windows 10/11 deja de estar en *beta*: la app ya se probó en un equipo Windows real.

## [1.3.1] - 2026-10-10

### Corregido
- Durante una subida (por ejemplo, desde «Subir a la PS5» en Convertir) la vista
  PS5 se veía como desconectada: unidades «Sin conexión», ruta vacía y botones
  bloqueados. Ahora sigue conectada y muestra la operación en curso; solo se
  pausan la navegación y las acciones hasta que el FTP vuelve a solo lectura.

## [1.3.0] - 2026-10-10

### Corregido
- Al reanudar una descarga de la PS5 el avance podía pasar del 100 % y el archivo
  crecer sin límite: el FTP de ps5upload acepta `REST` pero envía el archivo desde
  el principio, y se pegaba detrás de lo ya descargado. Ahora se verifica la
  reanudación (si la consola empieza de cero, se reescribe el archivo), se descarta
  un `.part` que no coincide y nunca se escribe más allá del tamaño esperado.
  La causa: ps5upload 6.x guarda la posición de `REST` en un entero de 32 bits, así
  que solo retoma en los primeros 2 GiB; por encima, la app vuelve a transferir ese
  archivo desde el principio (también en las subidas).

### Documentado
- ps5upload 7.0 eliminó el servidor FTP: la vista PS5 necesita la versión 6.x
  (la incluida en `payload/`).

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
- Bordes suavizados en los círculos de los pasos, el punto de conexión, las fichas,
  las etiquetas y el borde punteado de la zona para soltar juegos.

### Añadido
- Botón «Subir a la PS5» en cada juego convertido y «Subir completados a la PS5»
  para enviar todos los que aún no están en la consola.
- La subida omite los archivos que ya están en la PS5 con el mismo tamaño.
- Icono propio de la app en la ventana, la barra de tareas y los accesos directos
  de Linux y Windows (`assets/`, generado con `tools/make_icon.py`).
- Aviso de versión nueva: al abrirse, la app consulta la última *Release* publicada
  en GitHub y, si es más nueva, muestra el botón verde «Actualizar a vX.Y.Z», que
  abre su página. Sin conexión no muestra nada.
- Guía para publicar versiones como *Releases* de GitHub (`docs/DEVELOPMENT.md`) y
  capturas nuevas en el README.

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
