# Pestaña PS5: explorar, descargar, subir y reemplazar juegos

La pestaña **PS5** permite navegar por los archivos de una PS5 con el payload
de [ps5upload](https://github.com/phantomptr/ps5upload) cargado, descargar
archivos o carpetas completas, subir archivos, eliminar y **comprimir y
reemplazar** un juego directamente en la consola.

## Requisitos

- PS5 con jailbreak y el **payload de ps5upload** cargado (su helper escucha en el
  puerto **9120**). La carpeta [`payload/`](../payload/) incluye la versión probada
  (6.4.0) y explica cómo cargarla. No hace falta la app de escritorio de ps5upload.
- La PS5 y este equipo en la **misma red local** (mejor por cable).

## Primera conexión: emparejamiento

1. Carga el payload de ps5upload en la PS5.
2. En la app, abre la pestaña **PS5**, escribe la IP de la consola
   (*Ajustes → Red → Ver estado de la conexión*) y pulsa **Conectar**.
3. La PS5 muestra una notificación con un **código de 6 dígitos**. Escríbelo en
   el cuadro que abre la app (tienes menos de un minuto).

El emparejamiento se hace **una sola vez**: la app recuerda la consola y las
siguientes conexiones no piden código.

> [!IMPORTANT]
> La PS5 solo acepta emparejamientos nuevos durante los **5 minutos siguientes a
> cargar el payload** (si no tiene otro dispositivo emparejado). Si ves *"La PS5 no
> acepta emparejamientos nuevos"*, vuelve a cargar el payload y conecta enseguida.

## Cómo funciona

```mermaid
sequenceDiagram
    participant A as App
    participant H as Helper ps5upload (:9120)
    participant F as FTP de la PS5 (:2122)
    A->>F: ¿Está activo?
    alt FTP cerrado
        A->>H: Handshake cifrado (Noise XX) + emparejamiento (código)
        A->>H: ftp.start (solo lectura, usuario y contraseña aleatorios)
    end
    A->>F: Navegar (MLSD) y descargar (RETR, REST para reanudar)
```

- El FTP del helper no arranca solo. La app lo inicia con el protocolo **AVA1**
  de ps5upload, igual que su app de escritorio.
- Lo inicia en **solo lectura** y con **credenciales aleatorias**: otros equipos
  de la red no pueden usarlo para modificar la consola.
- El FTP queda activo hasta que la PS5 se reinicia o entra en reposo. Si otro
  programa lo inició con otras credenciales, la app lo reinicia con las suyas.

## Explorar

- **Doble clic** abre una carpeta; **⬆ Subir** vuelve a la anterior.
- El campo de ruta acepta cualquier ruta y ofrece accesos rápidos:
  `/data/homebrew` (la carpeta que vigila ShadowMount+), `/mnt/usb0`, `/mnt/ext0`…

## Descargar

1. Selecciona uno o varios archivos o carpetas (Ctrl/Mayús para varios).
2. Pulsa **⬇ Descargar selección**. La primera vez se pide la carpeta de destino.

| Característica | Detalle |
|---|---|
| Carpetas completas | Se recorren todas las subcarpetas, incluidas las vacías. |
| Reanudar | Cada archivo se escribe como `nombre.part`; si se corta o cancelas, la próxima descarga continúa desde donde quedó. |
| Ya descargado | Los archivos completos (mismo tamaño) se omiten. |
| Verificación | Cada archivo se compara con el tamaño que informa la PS5 antes de darlo por bueno. |
| Espacio | Se comprueba el espacio libre antes de empezar. |
| Nombres | Los caracteres que Windows no admite se cambian por `_`; un nombre que intente salir de la carpeta de destino (`../`) se descarta. |

Se puede seguir navegando mientras se descarga: cada descarga usa su propia
conexión.

## Comprimir y reemplazar un juego

Selecciona **una** carpeta de juego o imagen `.exfat`/`.ffpkg` y pulsa
**♻ Comprimir y reemplazar…**. La app:

1. **Descarga** el juego a `<carpeta de descargas>/ffpfsc-temporal/` (reanudable).
2. **Analiza** el juego y abre la ventana de compresión: modo (con peso
   estimado), núcleos, verificación completa y si borrar los temporales al final.
   Esa ventana muestra exactamente qué se subirá y qué se borrará.
3. **Comprime** a `.ffpfsc` con MkPFS (comprueba antes el espacio de este equipo).
4. **Comprueba el espacio** de la PS5 (`fs.freespace` del helper).
5. **Sube** el archivo como `Juego.ffpfsc.part` y **verifica** su tamaño.
6. Recién entonces **borra el original** en la PS5.
7. **Publica** el archivo renombrándolo a `Juego.ffpfsc` (misma carpeta).
8. Vuelve el FTP a **solo lectura** y, si lo elegiste, borra los temporales.

Una ventana resume todo en **3 pasos** (*Descarga → Compresión → Reemplazo*) y
muestra el subpaso actual, el **porcentaje**, la velocidad y el **tiempo restante**
estimado. Se puede **cancelar** en cualquier momento.

Si cancelas o falla, al volver a intentarlo con el mismo juego:

- la **descarga continúa** donde quedó (los archivos completos se omiten);
- la **compresión** se repite (MkPFS no puede reanudarse);
- la **subida continúa** solo si la parte que quedó en la PS5 pertenece al mismo
  archivo (se comparan sus últimos bytes); si no, empieza de cero.

| Situación | Qué hace la app |
|---|---|
| Caben ambos en la PS5 | Sube primero, verifica y después borra el original (orden seguro). |
| Solo cabe borrando el original | Pregunta antes de **borrar primero**; tu copia local se conserva hasta verificar la subida. |
| No cabe ni borrando | Se detiene sin tocar nada en la PS5. |
| Falla o cancelas | No se borra el original si la subida no se verificó; los archivos locales se conservan y la subida se reanuda. |

> [!WARNING]
> Cierra el juego en la PS5 antes de reemplazarlo. Si el juego estaba registrado
> desde la carpeta, ShadowMount+ registrará la imagen nueva al detectarla.

## Cortes de conexión y reintentos

- Si la conexión se corta durante una descarga o subida, la app **reintenta sola
  hasta 3 veces** (esperando 3, 10 y 20 s) y continúa donde quedó. La fila o la
  ventana muestran "Reintentando (1 de 3)…".
- Solo se reintentan los fallos transitorios (red, tiempo agotado, verificación);
  los definitivos (sin espacio, ruta protegida) se informan de inmediato.
- Si sigue fallando:
  - en el panel de transferencias, **↻ Reintentar fallidas** vuelve a encolar
    las descargas y subidas fallidas o canceladas (en sus mismas filas);
  - en "comprimir y reemplazar", **↻ Reintentar** retoma sin repetir lo hecho:
    no vuelve a comprimir si ya estaba comprimido ni a borrar el original si ya
    se había borrado.

## Subir y eliminar

- **⬆ Subir archivo…** sube archivos de este equipo a la carpeta abierta (como
  `.part`, verificados y luego renombrados; una subida cortada se reanuda).
- **🗑 Eliminar** borra en la PS5 los elementos seleccionados, tras confirmar con
  la lista exacta de rutas. Lo ejecuta el helper, que **se niega** a borrar raíces,
  carpetas de primer nivel (`/data`, `/mnt/usb0`) y puntos de montaje.
- Para escribir, la app reinicia el FTP con permiso de escritura **solo mientras
  dura la operación** y luego lo vuelve a dejar en solo lectura.

## Datos que guarda la app

En `~/.config/ffpfsc-converter/` (Linux) o `%APPDATA%\ffpfsc-converter\` (Windows):

| Archivo | Contenido |
|---|---|
| `settings.json` | Última IP y puerto, carpeta de descargas y credenciales del FTP que inició la app. |
| `ava1_identity.key` | Identidad de la app ante la PS5 (privada, permisos `600`). |
| `ava1_peers.json` | Clave de cada consola emparejada. Bórralo para volver a emparejar. |

## Solución de problemas

| Mensaje | Qué hacer |
|---|---|
| *No respondió en el puerto 9120* | El payload de ps5upload no está cargado. Cárgalo y reintenta. |
| *No acepta emparejamientos nuevos* | Vuelve a cargar el payload y conecta en menos de 5 minutos. |
| *No aceptó el código* | Pulsa **Conectar** otra vez; la PS5 muestra un código nuevo en cada intento. |
| *No es la PS5 con la que se emparejó* | Cambiaste de consola o reinstalaste: borra `ava1_peers.json` y vuelve a emparejar. |
| *Se perdió la conexión* | La PS5 entró en reposo o se reinició: carga el payload y conecta de nuevo. |
| *La PS5 no permite borrar esa ruta* | Es una raíz, una carpeta de primer nivel o un punto de montaje: el helper lo protege. |
| *La PS5 no tiene espacio* | Libera espacio en la consola o elige otro disco para el juego. |
| Transferencias de ~10 MB/s | Es el límite de la red, no de la app (medido: 9 MB/s con 1 conexión y 10 MB/s con 4). Conecta la PS5 **y** este equipo por cable a un router o switch gigabit. |
| *El original ya se borró…* | La subida falló tras borrar (solo en el modo "borrar primero"): sube el `.ffpfsc` de la carpeta temporal con **⬆ Subir archivo…**. |
