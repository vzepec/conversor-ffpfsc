<div align="center">

# 🎮 Conversor FFPFSC

### Comprime tus juegos de PS5 a `.ffpfsc` arrastrando y soltando

**Carpeta de juego · `.exfat` · `.ffpkg` &nbsp;→&nbsp; `.ffpfsc`**

[![Versión](https://img.shields.io/badge/versión-1.0.0-6366f1?style=for-the-badge)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](#-instalación)
[![MkPFS](https://img.shields.io/badge/motor-MkPFS-0ea5e9?style=for-the-badge)](https://github.com/PSBrew/MkPFS)
[![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)

<br/>

<img src="docs/assets/screenshot.png" alt="Ventana principal del Conversor FFPFSC" width="820"/>

<br/>

[Características](#-características) •
[Instalación](#-instalación) •
[Uso](#-uso) •
[Arquitectura](#-arquitectura) •
[Desarrollo](#-desarrollo) •
[Documentación](#-documentación)

</div>

---

## ✨ Características

<table>
<tr>
<td width="50%" valign="top">

### 🖱️ Arrastrar y soltar
Suelta una o varias carpetas o imágenes sobre la ventana. El programa
encuentra solo el `eboot.bin` o la imagen aunque esté varios niveles más
adentro.

### 🏷️ Nombre oficial del juego
Lee `sce_sys/param.json` (también dentro de `.exfat`) y muestra título,
Title ID y versión, priorizando el idioma del juego y luego español.

### 📏 Estimación antes de convertir
Calcula en segundos el **peso final** para cada modo comprimiendo una muestra
aleatoria de bloques, y avisa si no hay espacio suficiente en destino.

</td>
<td width="50%" valign="top">

### ⚡ Máxima velocidad
Usa todos los núcleos de la CPU y el backend **zlib-ng**, el único seguro para
el descompresor de la PS5.

### 📋 Cola de conversión
Convierte varios juegos seguidos con progreso, velocidad en vivo y registro
completo de MkPFS.

### 🛡️ Seguro por diseño
Verificación de estructura siempre (o completa, opcional), confirmación antes
de sobrescribir y borrado automático de salidas incompletas al cancelar o fallar.

</td>
</tr>
</table>

### Modos de compresión

| Modo | Nivel zlib | Cuándo usarlo |
|:-----|:----------:|:--------------|
| 🚀 **Máxima velocidad** *(por defecto)* | 3 | Casi siempre: compresión muy cercana al máximo en mucho menos tiempo. |
| ⚖️ **Equilibrado** | 6 | Un poco más pequeño a cambio de algo más de tiempo. |
| 🗜️ **Máxima compresión** | 9 | Cuando cada GB cuenta y no importa esperar. |

---

## 📦 Instalación

> **Requisitos:** Linux (probado en Ubuntu), Python 3.10+.
> El instalador añade `python3-tk` y `python3-venv` si faltan.

```bash
git clone git@github.com:vzepec/conversor-ffpfsc.git
cd conversor-ffpfsc
./instalar.sh
```

El instalador:

1. Crea un entorno virtual en `.venv/`.
2. Instala el conversor junto con [MkPFS](https://github.com/PSBrew/MkPFS), `zlib-ng` y `tkinterdnd2`.
3. Crea el acceso directo **Conversor FFPFSC** en el Escritorio y en el menú de aplicaciones.

---

## 🚀 Uso

```text
 ┌─────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
 │ 1. Arrastra el juego│ ──▶ │ 2. Revisa nombre y │ ──▶ │ 3. ▶ Convertir     │
 │    a la ventana     │     │    peso estimado   │     │    → Juego.ffpfsc  │
 └─────────────────────┘     └────────────────────┘     └────────────────────┘
```

Abre la app desde el Escritorio, o desde la terminal:

```bash
./abrir.sh                                  # ventana vacía
./abrir.sh "$HOME/Juegos/Mi Juego" otro.exfat   # con juegos ya en la cola
```

📖 Guía completa con opciones y preguntas frecuentes: **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**

---

## 🏗️ Arquitectura

Arquitectura en capas donde **las dependencias solo apuntan hacia abajo** y la
interfaz nunca habla directamente con MkPFS:

```mermaid
flowchart LR
    UI["🖼️ ui<br/><sub>Tkinter</sub>"] --> SVC["⚙️ services<br/><sub>casos de uso</sub>"]
    SVC --> INFRA["🔌 infrastructure<br/><sub>MkPFS · disco · SO</sub>"]
    UI --> DOM["📐 domain<br/><sub>modelos · eventos</sub>"]
    SVC --> DOM
    INFRA --> DOM
```

```text
src/ffpfsc_converter/
├── config.py          # todas las constantes
├── errors.py          # errores con mensajes para el usuario
├── domain/            # modelos y eventos — Python puro
├── infrastructure/    # adaptador MkPFS, sistema de archivos, escritorio
├── services/          # descubrir · metadatos · estimar · analizar · convertir
└── ui/                # ventana, presentadores (textos), tema, arrastrar y soltar
```

Los servicios corren en hilos de fondo y publican **eventos tipados** en una
cola; la ventana los consume en el hilo de Tkinter. Detalles, diagramas de
secuencia y decisiones técnicas en **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## 🧑‍💻 Desarrollo

```bash
./instalar.sh --dev            # + pytest y ruff
source .venv/bin/activate

pytest                         # tests
ruff check src tests           # lint
python -m ffpfsc_converter     # ejecutar desde el código
```

Este repositorio incluye **skills de Claude Code** en [`.claude/skills/`](.claude/skills/)
que estandarizan la arquitectura, el código limpio y las buenas prácticas:

| Skill | Define |
|:------|:-------|
| [`ffpfsc-architecture`](.claude/skills/ffpfsc-architecture/SKILL.md) | Capas, reglas de importación y dónde va cada cambio |
| [`ffpfsc-clean-code`](.claude/skills/ffpfsc-clean-code/SKILL.md) | Nombres, funciones, tipos, docstrings y manejo de errores |
| [`ffpfsc-best-practices`](.claude/skills/ffpfsc-best-practices/SKILL.md) | Hilos y Tkinter, MkPFS, tests, Git y checklist antes de commitear |

Más en **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**.

---

## 📚 Documentación

| Documento | Contenido |
|:----------|:----------|
| [📖 Guía de uso](docs/USER_GUIDE.md) | Formatos aceptados, opciones, preguntas frecuentes |
| [🏗️ Arquitectura](docs/ARCHITECTURE.md) | Capas, flujo, modelo de hilos, decisiones, cómo extender |
| [🧑‍💻 Desarrollo](docs/DEVELOPMENT.md) | Entorno, tests, flujo de Git, versiones |
| [📝 Changelog](CHANGELOG.md) | Historial de cambios |

---

## 🙏 Créditos

- **[MkPFS](https://github.com/PSBrew/MkPFS)** de PSBrew: el motor que genera las imágenes PFS/PFSC.
- **[zlib-ng](https://github.com/zlib-ng/zlib-ng)**: compresión rápida y compatible con la PS5.
- **[tkinterdnd2](https://github.com/Eliav2/tkinterdnd2)**: arrastrar y soltar en Tkinter.

> [!IMPORTANT]
> Esta herramienta está pensada para respaldar **juegos de tu propiedad**.
> No incluye ni distribuye contenido protegido por derechos de autor.

<div align="center">
<sub>Hecho con ☕ por <a href="https://github.com/vzepec">vzepec</a></sub>
</div>
