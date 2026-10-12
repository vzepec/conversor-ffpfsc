<div align="center">

<img src="assets/icon.png" alt="" width="84"/>

# Conversor FFPFSC

### Comprime tus juegos de PS5 a `.ffpfsc` o LZ4 arrastrando y soltando

**Carpeta de juego · `.exfat` · `.ffpkg` &nbsp;→&nbsp; `.ffpfsc` o LZ4 (experimental)**

[![Versión](https://img.shields.io/badge/versión-1.7.0-6366f1?style=for-the-badge)](CHANGELOG.md)
[![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](#-instalación)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](#-instalación)

<br/>

<img src="docs/assets/convertir.png" alt="Pestaña Convertir con dos juegos en la cola" width="820"/>
<br/><br/>
<img src="docs/assets/ps5.png" alt="Pestaña PS5 con las unidades, los archivos y las transferencias" width="820"/>

<br/>

[Qué hace](#-qué-hace) •
[Qué necesitas](#-qué-necesitas) •
[Instalación](#-instalación) •
[Cómo se usa](#-cómo-se-usa) •
[Preguntas frecuentes](#-preguntas-frecuentes) •
[Más información](#-más-información)

</div>

---

## 🎮 Qué hace

Los juegos de PS5 ocupan mucho espacio. Esta app los **comprime** para que ocupen
bastante menos (a menudo la mitad) y se sigan pudiendo jugar con **ShadowMount+** en
una PS5 con jailbreak.

- 🖱️ **Arrastra y suelta** la carpeta del juego (o su imagen `.exfat` / `.ffpkg`) en la
  ventana. La app encuentra el juego aunque esté dentro de otras carpetas.
- 🏷️ **Reconoce el juego**: muestra su nombre, su código (por ejemplo `PPSA01234`) y su versión.
- 📏 **Te dice cuánto pesará** antes de empezar, y avisa si no te alcanza el espacio.
- 📋 **Pon varios juegos en cola** y deja que se compriman uno tras otro.
- 🛡️ **Tu juego original nunca se modifica.** Si algo falla o cancelas, se borra lo que
  quedó a medias.
- 📶 **Gestiona la PS5 desde el PC** (pestaña **PS5**): mira el espacio libre, descarga,
  sube archivos o carpetas, borra, y **comprime y reemplaza** un juego que ya está en la
  consola en un solo paso.

### Dos formatos para elegir

| | `.ffpfsc` (recomendado) | LZ4 (experimental) |
|:--|:--|:--|
| **Qué es** | Una imagen comprimida que ShadowMount+ monta como cualquier juego | Una carpeta con los recursos del juego empaquetados en LZ4 |
| **Juegos** | Todos | Solo los compatibles (la app te lo indica) |
| **Para qué** | Ahorrar espacio | Que el juego cargue más rápido, aunque ahorre menos |
| **Dónde se comprime** | En tu PC | En tu PC |

> [!WARNING]
> **LZ4 es experimental.** Usa las herramientas de
> [ampr_emu](https://github.com/drakmor/ampr_emu), que todavía están en pruebas, y un juego
> convertido podría no arrancar. **Conserva el original** hasta comprobar que el
> convertido funciona. Guía: **[docs/LZ4.md](docs/LZ4.md)**.

---

## 🧰 Qué necesitas

- Un PC con **Windows 10/11** o **Linux** (probado en Ubuntu).
- Espacio libre en el disco para el juego comprimido.
- Para jugar: una **PS5 con jailbreak** y **ShadowMount+**.
- Para la pestaña PS5 (opcional): el payload **ps5upload 6.x** cargado en la consola. Viene
  incluido en la carpeta [`payload/`](payload/); los pasos están en [docs/PS5.md](docs/PS5.md).

---

## 📦 Instalación

<details open>
<summary><b>🪟 Windows 10/11</b></summary>

1. Instala [Python](https://www.python.org/downloads/windows/) (versión 3.10 o más nueva).
   Durante la instalación, marca la casilla **Add python.exe to PATH**.
2. Descarga este proyecto: botón verde **Code → Download ZIP**, y descomprímelo.
3. Haz doble clic en **`instalar.bat`** y espera a que termine.

Aparecerá el acceso directo **Conversor FFPFSC** en el Escritorio y en el menú Inicio.

</details>

<details open>
<summary><b>🐧 Linux</b></summary>

Abre una terminal y escribe:

```bash
git clone https://github.com/vzepec/conversor-ffpfsc.git
cd conversor-ffpfsc
./instalar.sh
```

Puede pedirte tu contraseña para instalar lo que falte. Al terminar tendrás el acceso
directo **Conversor FFPFSC** en el Escritorio y en el menú de aplicaciones.

</details>

El instalador también descarga los componentes de LZ4. Si en ese momento no tienes
internet, no pasa nada: todo lo demás funciona igual y puedes volver a instalar después.

📖 Problemas al instalar: **[docs/INSTALLATION.md](docs/INSTALLATION.md)**

---

## 🚀 Cómo se usa

1. Abre **Conversor FFPFSC**.
2. **Arrastra** la carpeta del juego (o su `.exfat` / `.ffpkg`) a la ventana, o usa
   **Elegir carpeta…** / **Elegir imagen…**.
3. Revisa el nombre del juego y el **peso estimado**.
4. Elige el **formato** (`.ffpfsc` o LZ4) y el **modo**:

   | Modo | Cuándo usarlo |
   |:--|:--|
   | 🚀 **Máxima velocidad** *(por defecto)* | Casi siempre: comprime casi igual que el máximo, en mucho menos tiempo. |
   | ⚖️ **Equilibrado** | Un poco más pequeño, a cambio de algo más de tiempo. |
   | 🗜️ **Máxima compresión** | Cuando cada GB cuenta y no te importa esperar. |

5. Pulsa **▶ Convertir**. Verás el avance, la velocidad y el tiempo que falta.
6. Cuando termine, pulsa **Subir a la PS5** en la fila del juego para enviarlo a la
   consola, o cópialo tú mismo a la carpeta `homebrew` de la PS5.

💡 **Rendimiento en la PS5**: actívalo con juegos grandes. Ocupan algo más, pero cargan más
rápido.

📖 Guía completa con todas las opciones: **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**

---

## ❓ Preguntas frecuentes

**¿Se borra o se modifica mi juego original?**
No. Para comprimir, la app solo lo lee. Nunca borra un juego por su cuenta: solo cuando tú
lo pides (**Eliminar** o **Comprimir y reemplazar**), siempre con confirmación y mostrando la ruta exacta. Al reemplazar, primero comprueba que la
copia comprimida esté bien.

**¿Cuánto tarda?**
Depende del juego y de tu PC: desde unos minutos hasta más de una hora en juegos de cientos
de GB. La app muestra el tiempo que falta.

**¿Y si se corta la conexión mientras subo un juego a la PS5?**
La subida se reintenta sola y, si hace falta, sigue desde donde quedó.

**¿Qué formato elijo?**
`.ffpfsc` si quieres ahorrar espacio y que funcione con cualquier juego. LZ4 solo si
quieres probar a que un juego compatible cargue más rápido (experimental).

**¿La app me avisa si hay una versión nueva?**
Sí: aparece un botón verde en la barra lateral.

📖 Más preguntas en **[docs/USER_GUIDE.md](docs/USER_GUIDE.md#6-preguntas-frecuentes)**

---

## 📚 Más información

| Documento | Para qué |
|:----------|:---------|
| [📖 Guía de uso](docs/USER_GUIDE.md) | Todas las opciones de la pestaña Convertir y preguntas frecuentes |
| [🎮 Pestaña PS5](docs/PS5.md) | Conectar la consola, descargar, subir, borrar y comprimir y reemplazar |
| [🧪 LZ4 (experimental)](docs/LZ4.md) | Comprimir en LZ4 y reemplazar juegos de la PS5 en LZ4 |
| [📦 Instalación](docs/INSTALLATION.md) | Pasos detallados y solución de problemas |
| [📝 Novedades](CHANGELOG.md) | Qué cambió en cada versión |
| [🛠️ Información técnica](docs/TECHNICAL.md) | Para desarrolladores: arquitectura, componentes y cómo contribuir |

---

## 🙏 Créditos

- **[MkPFS](https://github.com/PSBrew/MkPFS)** de PSBrew: el motor que crea los `.ffpfsc`.
- **[ps5upload](https://github.com/phantomptr/ps5upload)** de PhantomPtr: el payload de la PS5
  que usa la pestaña PS5.
- **[ampr_emu](https://github.com/drakmor/ampr_emu)** de drakmor: el formato LZ4 (AMPR).
- **[zlib-ng](https://github.com/zlib-ng/zlib-ng)** y **[tkinterdnd2](https://github.com/Eliav2/tkinterdnd2)**.

> [!IMPORTANT]
> Esta herramienta está pensada para respaldar **juegos de tu propiedad**.
> No incluye ni distribuye contenido protegido por derechos de autor.

<div align="center">
<sub>Hecho con ☕ por <a href="https://github.com/vzepec">vzepec</a></sub>
</div>
