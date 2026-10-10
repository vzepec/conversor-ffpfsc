# Instalación

El conversor funciona en **Linux** y en **Windows 10/11 de 64 bits** (**beta**:
el soporte para Windows aún no se ha validado en un equipo Windows real). En ambos
casos se instala dentro de un entorno virtual (`.venv/`) en la carpeta del
proyecto, así que no modifica el Python del sistema.

| | Linux | Windows |
|---|---|---|
| Python | 3.10 o superior | 3.10 o superior, de [python.org](https://www.python.org/downloads/windows/) |
| Instalador | `./instalar.sh` | `instalar.bat` |
| Lanzador | `./abrir.sh` | `abrir.bat` o acceso directo |
| Acceso directo | Escritorio y menú de aplicaciones | Escritorio y menú Inicio |
| Abrir carpeta de salida | `xdg-open` | Explorador de archivos |
| Cancelar conversión | `SIGTERM` al grupo de procesos | `taskkill /T` (proceso y procesos hijo) |

Dependencias que se instalan automáticamente: [MkPFS](https://github.com/PSBrew/MkPFS),
`zlib-ng`, `tkinterdnd2` (arrastrar y soltar) y las dependencias de MkPFS.

## Linux

```bash
git clone git@github.com:vzepec/conversor-ffpfsc.git
cd conversor-ffpfsc
./instalar.sh
```

El instalador:

1. Instala `python3-tk` y `python3-venv` con `apt` si faltan (pide tu contraseña).
2. Crea `.venv/` e instala el conversor y sus dependencias.
3. Crea el acceso directo **Conversor FFPFSC** en el Escritorio y en el menú.

En distribuciones sin `apt`, instala antes los equivalentes de `python3-tk` y
`python3-venv` con tu gestor de paquetes.

## Windows (beta)

### 1. Instalar Python

1. Descarga **Python 3.10 o superior (64 bits)** desde
   [python.org/downloads/windows](https://www.python.org/downloads/windows/).
2. En el instalador marca **Add python.exe to PATH**.
3. Deja marcada la opción **tcl/tk and IDLE** (viene marcada por defecto): es
   la que instala tkinter, necesario para la ventana.

> La versión de Python de Microsoft Store también funciona, pero se recomienda
> la de python.org.

### 2. Descargar el conversor

- Con Git: `git clone git@github.com:vzepec/conversor-ffpfsc.git`
- Sin Git: en GitHub, **Code → Download ZIP** y descomprime el archivo en una
  carpeta con una ruta corta, por ejemplo `C:\ConversorFFPFSC`.

### 3. Ejecutar el instalador

Haz doble clic en **`instalar.bat`**. El instalador:

1. Comprueba que hay Python 3.10+ con tkinter.
2. Crea `.venv\` e instala el conversor y sus dependencias.
3. Crea el acceso directo **Conversor FFPFSC** en el Escritorio y en el menú Inicio.

`instalar.bat` ejecuta `instalar.ps1` con `-ExecutionPolicy Bypass` solo para
ese proceso; no cambia la política de ejecución del sistema.

### 4. Abrir

- Doble clic en el acceso directo **Conversor FFPFSC**, o
- arrastra la carpeta del juego **sobre el acceso directo** para abrir la app
  con ese juego ya en la cola, o
- desde una terminal: `abrir.bat "D:\Juegos\Mi Juego"`.

## Pestaña PS5 (opcional)

Para explorar, descargar, subir o reemplazar juegos directamente en la consola
no hace falta instalar nada más en el equipo, ni en Linux ni en Windows: la PS5
necesita el payload de ps5upload incluido en [`payload/`](../payload/) (cómo
cargarlo, versión y SHA-256 en su README). El uso está en [PS5.md](PS5.md).

## Actualizar

Descarga la versión nueva (`git pull` o un ZIP nuevo en la misma carpeta) y
vuelve a ejecutar el instalador. El entorno virtual se reutiliza.

## Desinstalar

1. Borra la carpeta del proyecto (incluye `.venv/`).
2. Borra los accesos directos:
   - Linux: `~/.local/share/applications/conversor-ffpfsc.desktop` y el del Escritorio.
   - Windows: los del Escritorio y del menú Inicio (`Conversor FFPFSC.lnk`).

## Solución de problemas

| Problema | Solución |
|----------|----------|
| Windows: *"No se encontró Python"* | Reinstala Python marcando **Add python.exe to PATH**, o verifica que `py --version` funciona en una terminal nueva. |
| Windows: *"Falta tkinter"* | Ejecuta de nuevo el instalador de Python → **Modify** → marca **tcl/tk and IDLE**. |
| Windows: SmartScreen bloquea `instalar.bat` | **Más información → Ejecutar de todas formas**. Ocurre con cualquier script descargado. |
| Windows: errores con rutas muy largas | Mueve el proyecto y los juegos a rutas cortas (`C:\ConversorFFPFSC`, `D:\Juegos`) o activa las [rutas largas de Windows](https://learn.microsoft.com/es-es/windows/win32/fileio/maximum-file-path-limitation). |
| No aparece la zona de "arrastrar y soltar" | `tkinterdnd2` no se pudo cargar. La app funciona igual con **clic para elegir**; reinstala con el instalador. |
| El destino no admite el archivo | El `.ffpfsc` puede pesar decenas de GB: el disco de destino debe ser **NTFS, exFAT o ext4**, nunca FAT32 (máximo 4 GB por archivo). |
| La conversión es muy lenta | Revisa que el modo sea **Máxima velocidad** y que **Núcleos CPU** use todos los núcleos. Los discos USB lentos son el cuello de botella más común. |

## Plataformas no soportadas

- **macOS**: el código ya contempla macOS (abre la carpeta de salida con `open`
  y cancela igual que en Linux), pero no hay instalador ni se ha probado.
- **Windows de 32 bits / ARM**: no se garantiza que existan paquetes
  precompilados de todas las dependencias.
