# Guía de uso

> Instalación en Linux y Windows: [INSTALLATION.md](INSTALLATION.md).

## 1. Qué puedo convertir

| Origen | Qué se espera |
|--------|---------------|
| **Carpeta de juego** | Una carpeta que contenga `eboot.bin` y `sce_sys/` (puede estar hasta 3 niveles más adentro de la carpeta que arrastras). |
| **Imagen `.exfat`** | Imagen exFAT de un juego. |
| **Imagen `.ffpkg`** | Imagen del juego en formato ffpkg. |
| **Carpeta con una imagen dentro** | Si la carpeta no tiene `eboot.bin`, se usa el `.exfat`/`.ffpkg` más grande que haya dentro (hasta 2 niveles). |

El resultado es un único archivo **`.ffpfsc`** (PFS comprimido) con el nombre
de la carpeta o imagen original.

## 2. La ventana

A la izquierda, la **barra lateral** tiene las dos secciones (**Convertir** y
**PS5**, cada una con su contador), el estado de la conexión con la consola y el
selector de **tema**: *Sistema* (por defecto, sigue al tema claro u oscuro del
equipo), *Claro* u *Oscuro*. La elección se recuerda.

Cuando hay una **versión nueva** publicada aparece el botón verde **Actualizar a
vX.Y.Z**: abre la página de la versión, con sus novedades y cómo instalarla (ver
[INSTALLATION.md](INSTALLATION.md#actualizar)).

## 3. Pasos

1. Abre **Conversor FFPFSC** desde el Escritorio, el menú de aplicaciones (Linux)
   o el menú Inicio (Windows).
2. **Arrastra** una o varias carpetas/imágenes a la zona punteada de arriba
   (o haz clic en ella / usa **Elegir carpeta…** o **Elegir imagen…**).
3. Espera unos segundos: cada juego aparece en la **cola** con su nombre oficial,
   Title ID, versión, tamaño y **peso final estimado** (en verde).
4. Elige el **Modo** de compresión (la estimación se actualiza al instante).
5. Opcional: cambia la carpeta de destino con **Cambiar**.
6. Pulsa **Convertir**. Los juegos se convierten uno detrás de otro; cada fila
   muestra la etapa, una barra de avance, la velocidad y el tiempo restante.

### Subir el juego comprimido a la PS5

Cuando un juego termina de comprimirse aparece el botón **Subir a la PS5** en su
fila. **Subir completados a la PS5**, abajo, sube todos los comprimidos que aún
no están en la consola. Eliges la carpeta de destino (por defecto
`/data/homebrew`, la que vigila ShadowMount+) y el avance se ve en la misma fila.
Si el archivo ya está en la PS5 con el mismo tamaño, no se vuelve a enviar.

- Si la PS5 ya está vinculada pero no conectada, la app ofrece conectar y la
  subida empieza sola.
- Si nunca la vinculaste, muestra los pasos (cargar el payload, escribir la IP,
  «Conectar» y el código de 6 dígitos) y te lleva a la sección **PS5**. La subida
  queda en espera y empieza en cuanto te conectes.

La subida es la misma de la sección PS5: se verifica, se reanuda y se reintenta
sola ante cortes. Más detalles en [PS5.md](PS5.md).

## 4. Opciones

| Opción | Efecto |
|--------|--------|
| **Máxima velocidad (nivel 3)** | Recomendado. Casi la misma compresión que el nivel 9 en mucho menos tiempo. |
| **Equilibrado (nivel 6)** | Algo más pequeño, algo más lento. |
| **Máxima compresión (nivel 9)** | El más pequeño; puede tardar varias veces más. |
| **Núcleos** | Por defecto todos (**−** / **+**). Bájalo si quieres seguir usando el equipo mientras convierte. |
| **Guardar en** | Por defecto junto al juego original. |
| **Verificación completa** | Relee y comprueba cada bloque al terminar. Más lento, máxima seguridad. Sin marcarla se verifica solo la estructura. |

La app **recuerda** el modo, los núcleos, la verificación y la carpeta de destino
entre sesiones, además del tamaño de la ventana y la última vista abierta. Con
**Usar «junto a cada juego»** vuelves a guardar los `.ffpfsc` al lado del original.

## 5. Antes de empezar, el programa comprueba

- Si el `.ffpfsc` **ya existe**, pregunta si sobrescribirlo.
- Si el **espacio libre** en destino es menor que el peso estimado + 5 %,
  avisa y pregunta si continuar.

## 6. Preguntas frecuentes

**¿Puedo cancelar?** Sí, con **Cancelar**. El archivo a medio escribir se
borra automáticamente; los juegos que faltaban quedan en la cola.

**La estimación dice "+X %".** Ese juego casi no se comprime (datos ya
comprimidos o cifrados); el resultado ocuparía algo más por las tablas PFS.

**"No encontré un juego dentro de…"** La carpeta no tiene `eboot.bin` ni
ninguna imagen `.exfat`/`.ffpkg` cerca. Arrastra la carpeta correcta.

**¿Dónde veo los detalles?** Despliega **Registro técnico** (abajo a la
izquierda): muestra el comando exacto de MkPFS y toda su salida, útil para
reportar errores.
