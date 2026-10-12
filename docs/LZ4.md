# Compresión LZ4 (formato AMPR) — EXPERIMENTAL

Se puede comprimir en LZ4 **en la PS5** (sección PS5, con exfat2ampr) o **en este
equipo** (vista Convertir, con ampr_emu; ver [más abajo](#en-este-equipo-vista-convertir)).

> [!WARNING]
> Función **experimental**. La conversión la hace
> [exfat2ampr](https://github.com/ViiNCENZO10/exfat2ampr) dentro de la consola, y
> su propio autor indica que **no la probó en una PS5**: valida el formato con las
> herramientas de referencia, no la ejecución del juego. Empieza con un juego
> pequeño y **conserva el original** hasta comprobar que el convertido funciona.

El botón **Comprimir LZ4 en la PS5…** de la sección **PS5** pide a exfat2ampr que
convierta, en la propia consola, la carpeta o imagen `.exfat`/`.ffpkg`
seleccionada al formato **AMPR LZ4**. La app no transfiere el juego: solo da las
órdenes, muestra el avance en **Transferencias** y deja cancelar o reanudar.

## AMPR LZ4 frente a `.ffpfsc`

| | `.ffpfsc` (vista Convertir) | AMPR LZ4 (esta función) |
|---|---|---|
| Dónde se comprime | En este equipo, con MkPFS | En la PS5, con exfat2ampr |
| Resultado | Una imagen PFS comprimida con zlib | Una **carpeta** en `homebrew/` con los recursos empaquetados en LZ4 (`ampr_assets-NNN.pak`) |
| Cómo lo lee la consola | ShadowMountPlus monta la imagen | El juego lee sus recursos a través de `libSceAmpr` y el emulador AMPR (`fakelib/libSceAmpr.sprx`) |
| Juegos compatibles | Todos | Solo los que usan `libSceAmpr` |
| Transferencia por la red | Hay que subir el `.ffpfsc` | Ninguna: todo ocurre en la consola |

## Requisitos

- PS5 con jailbreak y un **cargador de ELF en el puerto 9021** (etaHEN o elfldr).
- **ShadowMountPlus 1.7 o posterior** para convertir imágenes `.exfat`/`.ffpkg` y
  para que el juego convertido cargue el emulador AMPR.
- La sección **PS5** conectada (ps5upload, ver [PS5.md](PS5.md)): la app usa el FTP
  para elegir el juego y la API de exfat2ampr (puerto **6972**) para convertirlo.
- **`exfat2ampr.elf` 1.45**: lo descarga el instalador en `third_party/` desde
  <https://github.com/ViiNCENZO10/exfat2ampr/releases> y comprueba su SHA-256. Si
  falta (instalación sin internet), la app te pide elegirlo una vez.

## Primer uso

1. En la sección **PS5**, selecciona **una** carpeta de juego o imagen y pulsa
   **Comprimir LZ4 en la PS5…**.
2. Si exfat2ampr no está en marcha, la app envía sola el `exfat2ampr.elf` instalado
   (o el que elegiste) al cargador de ELF (9021) y espera a que responda (hasta 30 s).
3. Al arrancar, la PS5 muestra una notificación con la dirección y un **código de
   6 dígitos** (`http://IP:6972/  code 123456`). Escríbelo en la ventana de
   emparejamiento. Se pide **una sola vez** por consola: el token se guarda en la
   app y en la PS5, y sobrevive a reinicios de exfat2ampr.
4. Tras 5 códigos incorrectos, exfat2ampr se bloquea un minuto y **cambia el
   código**: vuelve a cargarlo para ver el nuevo.

## La ventana de compresión

Antes de abrirla, exfat2ampr comprueba el juego y el destino. La ventana muestra:

- **Compatibilidad**: «✓ Compatible» si el juego usa `libSceAmpr`. Si no lo usa
  (código `not_ampr`), aparece «✗ No compatible» y no se puede iniciar: comprimirlo
  lo dañaría. Con un eboot cifrado queda «sin confirmar»; con una imagen sin montar
  se comprueba al empezar.
- **Destino**: las unidades de la PS5 con su espacio libre. Se sugiere la misma
  unidad del original (si no, la interna). El juego queda en `<unidad>/homebrew/<TITLE_ID>`;
  si esa carpeta es el propio original (por ejemplo, un juego ya en `/data/homebrew/PPSA01234`
  comprimido en la misma unidad), se guarda en `<TITLE_ID>-LZ4` para no pisarlo.
- **Modo**: Rápido (LZ4 nivel 1), **Equilibrado** (LZ4 HC 9, recomendado) o Máximo
  (LZ4 HC 12). Los modos HC tardan más en comprimir, pero se leen igual de rápido.
- **Verificar al terminar** (activado): decodifica y comprueba cada bloque.
- **Original**: conservarlo (por defecto) o borrarlo al terminar bien. Borrarlo pide
  una confirmación extra con la ruta exacta.
- **Reemplazar el comprimido anterior**: obligatorio si ya hay uno en el destino
  (aviso `already_exists`).
- Las **rutas exactas** que se crearán, reemplazarán o borrarán.

Al aceptar, se repite la comprobación contra el destino elegido; si falla (falta
espacio, el juego está abierto, la unidad no admite escritura…), no se inicia y
se explica el motivo.

## Avance, pausa y cancelación

La fila de **Transferencias** muestra la fase (analizar, comprimir, verificar…),
el porcentaje, la velocidad y el tiempo restante. La conversión sigue en la PS5
aunque cierres la app; al volver a conectar, la app la retoma en una fila nueva.

| Estado | Qué significa | Qué hacer |
|---|---|---|
| **En pausa: se reanudará al cerrar el juego** | Abriste en la PS5 el juego que se convierte (`paused_game`) | Nada: al cerrarlo, exfat2ampr reanuda solo. **Cancelar** sigue disponible |
| **En espera** | ShadowMountPlus no monta imágenes con un juego o app abiertos (`smp_busy`) | Cierra lo que esté abierto en la PS5 |
| **En pausa** + **Reanudar** | Pausa manual, destino lleno, destino u origen desconectado (`paused_user`, `paused_full`, `paused_dest`, `paused_source`) | Corrige la causa (libera espacio, reconecta la unidad) y pulsa **Reanudar** |
| **Cancelado** | Cancelaste: exfat2ampr borró la carpeta a medias | Nada: el original sigue intacto |
| **✓ Comprimido** | Terminó | Prueba el juego antes de borrar el original |

**Cancelar** pide confirmación mostrando la carpeta que se borrará. La reanudación
continúa desde el último punto guardado; si el original cambió desde la pausa,
exfat2ampr la rechaza y hay que empezar de nuevo.

## Riesgos y recomendaciones

- **Conserva el original** hasta abrir el juego convertido y jugar un rato
  (cargar partida, cambiar de zona). Bórralo después a mano si todo va bien.
- Si el juego convertido no arranca, revisa en ShadowMountPlus que su *fakelib* no
  esté «Desactivado» (exfat2ampr lo cambia a «Emuladores» si hace falta).
- El registro de exfat2ampr está en la PS5, en `/data/exfat2ampr/exfat2ampr.log`;
  el de la app, en **Registros** (barra lateral).
- Solo se envía el ELF a tu consola si exfat2ampr no responde. Lo descarga el
  instalador, desde la página oficial y con su huella comprobada; la app no.

## En este equipo (vista Convertir)

Elige **Formato → LZ4 (experimental)** en la vista Convertir. La cola muestra si cada
juego es **compatible** (busca `libSceAmpr` en `eboot.bin` y `sce_module/`) y su peso
estimado en LZ4; las imágenes `.exfat`/`.ffpkg` y los juegos no compatibles se omiten
avisando antes. Los modos equivalen a LZ4 rápido (Máxima velocidad), HC 9
(Equilibrado) y HC 12 (Máxima compresión).

La conversión usa las herramientas en Python de
[ampr_emu](https://github.com/drakmor/ampr_emu) 0.4.2.1 (las descarga el instalador):

1. Índice del juego (`build_ampr_index.py`), escrito fuera del original.
2. Perfil genérico: las mismas reglas que exfat2ampr (quedan sin empaquetar
   ejecutables, `sce_sys/`, `sce_module/`, vídeo, audio comprimido, `.pak`/`.utoc`,
   archivos de la raíz…; el audio usa bloques de 16 KiB).
3. Paquetes LZ4 (`ampr_pack.py pack`) con deduplicación.
4. Verificación de cada bloque y comparación byte a byte con el original.
5. Carpeta final `<juego>-LZ4` junto a donde iría el `.ffpfsc`: lo que queda suelto,
   los paquetes, `ampr_emu.index` y `fakelib/libSceAmpr.sprx`.

El original **solo se lee**. Lo temporal (`.<juego>-LZ4.lz4-temporal`) y lo parcial
(`<juego>-LZ4.parcial`) van en la carpeta de destino y se borran al terminar, fallar o
cancelar; una conversión anterior en la misma ruta solo se reemplaza al final. Espacio
necesario: el peso estimado (los paquetes se mueven, no se copian). Subir la carpeta a
la PS5 desde la app todavía no está disponible: cópiala a `homebrew/` por FTP. El juego
necesita que ShadowMountPlus cargue su `fakelib`: si no arranca, revisa que su opción
de fakelib no esté en «Desactivado» (exfat2ampr la ajusta solo; desde el PC no se puede).

## Datos que guarda la app

En `settings.json` (ver [PS5.md](PS5.md#datos-que-guarda-la-app)):
`e2a_elf_path` (ruta del `exfat2ampr.elf` elegido) y `e2a_tokens` (token de
emparejamiento por IP de consola). Si exfat2ampr deja de aceptar el token, la app
lo olvida y vuelve a pedir el código.

## Mensajes

Las ventanas usan frases cortas y sin términos técnicos. El detalle (códigos de
exfat2ampr como `not_ampr` o `queue_full`, la respuesta en inglés y los puertos)
queda en **Registros** (barra lateral).

| Mensaje | Qué hacer |
|---|---|
| *No se pudo iniciar exfat2ampr. Carga etaHEN (o elfldr)…* | No hay cargador de ELF en el puerto 9021: cárgalo y reintenta. |
| *exfat2ampr no arrancó en la PS5* | Mira si la PS5 mostró algún error; reintenta o envía el ELF a mano. |
| *exfat2ampr no responde* | La PS5 se apagó, entró en reposo o exfat2ampr se cerró (puerto 6972). |
| *No se puede comprimir eso* | Elige la carpeta del juego (la que tiene `eboot.bin`) o su imagen. |
| *Demasiados códigos incorrectos* | Espera un minuto y vuelve a cargar exfat2ampr para ver el código nuevo. |
| *✗ No compatible* | Ese juego no admite AMPR: usa la vista **Convertir** (`.ffpfsc`). |
| *…Los detalles están en Registros* | Error poco habitual: abre **Registros** para ver el código de exfat2ampr. |
