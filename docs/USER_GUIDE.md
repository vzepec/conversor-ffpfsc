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

## 2. Pasos

1. Abre **Conversor FFPFSC** desde el Escritorio, el menú de aplicaciones (Linux)
   o el menú Inicio (Windows).
2. **Arrastra** una o varias carpetas/imágenes a la zona oscura superior
   (o haz clic en ella / usa **+ Archivo .exfat…**).
3. Espera unos segundos: aparecen el **nombre oficial**, el **tamaño** y el
   **peso final estimado**.
4. Elige el **Modo** de compresión (la estimación se actualiza al instante).
5. Opcional: cambia la carpeta de destino con **Cambiar…**.
6. Pulsa **▶ Convertir**. Los juegos se convierten uno detrás de otro.

## 3. Opciones

| Opción | Efecto |
|--------|--------|
| **Máxima velocidad (nivel 3)** | Recomendado. Casi la misma compresión que el nivel 9 en mucho menos tiempo. |
| **Equilibrado (nivel 6)** | Algo más pequeño, algo más lento. |
| **Máxima compresión (nivel 9)** | El más pequeño; puede tardar varias veces más. |
| **Núcleos CPU** | Por defecto todos. Bájalo si quieres seguir usando el equipo mientras convierte. |
| **Guardar en** | Por defecto junto al juego original. |
| **Verificación completa** | Relee y comprueba cada bloque al terminar. Más lento, máxima seguridad. Sin marcarla se verifica solo la estructura. |

## 4. Antes de empezar, el programa comprueba

- Si el `.ffpfsc` **ya existe**, pregunta si sobrescribirlo.
- Si el **espacio libre** en destino es menor que el peso estimado + 5 %,
  avisa y pregunta si continuar.

## 5. Preguntas frecuentes

**¿Puedo cancelar?** Sí, con **■ Cancelar**. El archivo a medio escribir se
borra automáticamente; los juegos que faltaban quedan en la cola.

**La estimación dice "+X %".** Ese juego casi no se comprime (datos ya
comprimidos o cifrados); el resultado ocuparía algo más por las tablas PFS.

**"No encontré un juego dentro de…"** La carpeta no tiene `eboot.bin` ni
ninguna imagen `.exfat`/`.ffpkg` cerca. Arrastra la carpeta correcta.

**¿Dónde veo los detalles?** En el registro (recuadro inferior) aparece el
comando exacto de MkPFS y toda su salida, útil para reportar errores.
