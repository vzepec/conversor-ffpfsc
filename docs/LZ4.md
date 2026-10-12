# Compresión LZ4 (formato AMPR) — EXPERIMENTAL

La app comprime en LZ4 **en este equipo**, de dos formas:

- **Vista Convertir**: eliges **Formato → LZ4 (experimental)** y obtienes una carpeta
  `<juego>-LZ4` que luego subes a la PS5.
- **Comprimir y reemplazar** (sección PS5): descarga el juego de la consola, lo
  comprime en LZ4 en el PC, lo sube y reemplaza al original. Ver
  [más abajo](#comprimir-y-reemplazar-en-la-ps5).

> [!WARNING]
> Función **experimental**. Usa las herramientas de
> [ampr_emu](https://github.com/drakmor/ampr_emu), que todavía están en pruebas, y un
> juego convertido podría no arrancar. Empieza con un juego pequeño y **conserva el
> original** hasta comprobar que el convertido funciona.

## AMPR LZ4 frente a `.ffpfsc`

| | `.ffpfsc` | AMPR LZ4 |
|---|---|---|
| Herramienta | MkPFS | ampr_emu (herramientas en Python) |
| Resultado | Una imagen PFS comprimida con zlib | Una **carpeta** con los recursos empaquetados en LZ4 (`ampr_assets-NNN.pak`) |
| Cómo lo lee la consola | ShadowMountPlus monta la imagen | El juego lee sus recursos a través de `libSceAmpr` y el emulador AMPR (`fakelib/libSceAmpr.sprx`) |
| Juegos compatibles | Todos | Solo carpetas de juegos que usan `libSceAmpr` |

## Requisitos

- Las herramientas de ampr_emu 0.4.2.1 y `libSceAmpr.sprx`: los descarga el
  instalador en `third_party/` desde la página oficial y comprueba su SHA-256. Si
  faltan (instalación sin internet), vuelve a ejecutar el instalador.
- **ShadowMountPlus** con su opción de *fakelib* activa, para que el juego cargue
  el emulador AMPR.

## Compatibilidad

La app busca `libSceAmpr` en `eboot.bin` y en `sce_module/`. Las imágenes
`.exfat`/`.ffpkg` no se pueden revisar por dentro, así que LZ4 solo admite
**carpetas** de juego. Un juego no compatible aparece como «No compatible con LZ4».

## Vista Convertir

Elige **Formato → LZ4 (experimental)**. Se oculta «Rendimiento en la PS5», que solo usa
`.ffpfsc`. **Verificación completa** sigue disponible y en LZ4 viene **activada**: compara
el resultado con el original al terminar (paso 4). Apagarla ahorra tiempo, pero un paquete
dañado solo se notaría en la PS5; cada formato recuerda su propio valor. La cola muestra
si cada juego es compatible y su peso estimado; las imágenes y los juegos no compatibles
se omiten avisando antes. Los modos equivalen a LZ4 rápido (Máxima velocidad), HC 9
(Equilibrado) y HC 12 (Máxima compresión).

Pasos de la conversión:

1. Índice del juego (`build_ampr_index.py`), escrito fuera del original.
2. Perfil genérico: quedan sin empaquetar ejecutables, `sce_sys/`, `sce_module/`,
   vídeo, audio comprimido, `.pak`/`.utoc`, archivos de la raíz…; el audio usa bloques
   de 16 KiB.
3. Paquetes LZ4 (`ampr_pack.py pack`) con deduplicación.
4. Verificación de cada bloque y comparación byte a byte con el original (si
   **Verificación completa** está activada).
5. Carpeta final `<juego>-LZ4` junto a donde iría el `.ffpfsc`: lo que queda suelto,
   los paquetes, `ampr_emu.index` y `fakelib/libSceAmpr.sprx`.

El original **solo se lee**. Lo temporal (`.<juego>-LZ4.lz4-temporal`) y lo parcial
(`<juego>-LZ4.parcial`) van en la carpeta de destino y se borran al terminar, fallar o
cancelar; una conversión anterior en la misma ruta solo se reemplaza al final. Lo que
queda sin empaquetar se **enlaza** al original si está en el mismo disco (no ocupa espacio
extra: son los mismos archivos, no los edites en la carpeta nueva); si no, se copia. Espacio
necesario: el de los paquetes, más lo suelto si la salida está en otro disco. El peso
estimado simula cómo ampr_pack ubica los bloques en páginas de 64 KiB.

Para llevarla a la PS5 usa **Subir a la PS5** en la fila del juego (o **Subir a la
PS5… → Carpeta…** en la sección PS5): sube la carpeta completa a `<nombre>.part/` y la
publica con su nombre al final.

## Comprimir y reemplazar en la PS5

En la ventana de **Comprimir y reemplazar** (sección PS5) aparece **Formato** cuando el
original es una carpeta. **LZ4** queda desactivado, con el motivo, si el juego no es
compatible o faltan los componentes. Con LZ4 se oculta «Rendimiento en la PS5» y
**Verificación completa** empieza activada (puedes apagarla). Además:

- La carpeta LZ4 ocupa el lugar del original **con el mismo nombre**, así que la ruta
  del juego en la PS5 no cambia.
- Se sube primero a `<nombre>.part/`; cada archivo se comprueba con **CRC32**. Si alguno
  no coincide, se borra solo ese en la PS5 y el original queda intacto; **Reintentar**
  vuelve a subir solo lo que falta.
- Una vez verificada, se borra el original y la carpeta se renombra con su nombre.
- Si la PS5 no tiene espacio para ambos a la vez, la app pide confirmación para borrar
  antes el original (la copia descargada se conserva hasta terminar).

El resto del flujo (descarga verificada, FTP con escritura solo durante el reemplazo,
borrar los temporales al terminar) es igual que con `.ffpfsc`: ver [PS5.md](PS5.md).

## Riesgos y recomendaciones

- **Conserva el original** hasta abrir el juego convertido y jugar un rato
  (cargar partida, cambiar de zona). Con «Comprimir y reemplazar», desactiva
  **Borrar los temporales** si quieres guardar la copia descargada como respaldo.
- Si el juego convertido no arranca, revisa en ShadowMountPlus que su opción de
  *fakelib* no esté en «Desactivado» (desde el PC no se puede cambiar).
- El detalle de cada conversión está en **Registros** (barra lateral).
