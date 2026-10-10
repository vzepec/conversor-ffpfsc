# Desarrollo

## Entorno

```bash
# Linux
./instalar.sh --dev          # crea .venv e instala el paquete editable + pytest + ruff
source .venv/bin/activate

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File instalar.ps1 -Dev
.venv\Scripts\activate
```

## Comandos

| Tarea | Comando |
|-------|---------|
| Ejecutar la app | `./abrir.sh` / `abrir.bat` o `python -m ffpfsc_converter [rutas…]` |
| Tests | `pytest` |
| Lint | `ruff check src tests tools` |
| Lint con arreglos automáticos | `ruff check src tests tools --fix` |
| Estándares (≤ 250 líneas, docstrings) | `python tools/check_standards.py` |

Antes de cada commit debe pasar:

```bash
ruff check src tests tools && python tools/check_standards.py && pytest
```

`pytest` también ejecuta el verificador de estándares (`test_code_standards.py`),
así que un archivo de más de 250 líneas o una docstring incompleta hace fallar
los tests.

## Tests

| Archivo | Cubre |
|---------|-------|
| `test_discovery.py` | búsqueda de `eboot.bin`/imágenes, errores, ruta de salida |
| `test_metadata.py` | parseo de `param.json`, idiomas, *best effort* |
| `test_estimator.py` | estimación determinista, datos compresibles e incompresibles |
| `test_mkpfs_adapter.py` | comando `mkpfs pack`, parseo de progreso, corte de líneas `\r`/`\n` |
| `test_conversion.py` | cola, fallo, cancelación y error al lanzar (con `FakeProcess`) |
| `test_presenters.py` | todos los textos que ve el usuario |
| `test_preflight.py` | comprobación de espacio libre |
| `test_platform.py` | comandos y opciones por sistema operativo (Linux, macOS, Windows) |
| `test_ftp_listing.py` | interpretación de MLSD/LIST y nombres inseguros |
| `test_remote_browser.py` | cliente FTP y explorador contra un FTP real local (`pyftpdlib`) |
| `test_downloads.py` | descargas de carpetas, reanudación, cancelación, falta de espacio |
| `test_download_resume.py` | reanudación verificada: servidor que ignora `REST`, `.part` dañado, tope de tamaño |
| `test_ftp_launcher.py` | inicio del FTP con una sesión AVA1 simulada (emparejamiento, reinicio, errores) |
| `test_ava1_vectors.py` | cliente AVA1 contra los vectores oficiales de ps5upload |
| `test_explorer_support.py` | textos de la vista PS5, ajustes, progreso y almacén de confianza |
| `test_pipeline.py` | comprimir y reemplazar: orden seguro, poco espacio, cancelación |
| `test_remote_changes.py` | eliminar y subir (reanudación), plan y estrategia de espacio |
| `test_preferences.py` | validación de las opciones y del tamaño de ventana guardados |
| `test_integrity.py` | CRC32 local, comparación con la PS5 (`FakeConsole`) y mensajes |
| `test_update_check.py` | aviso de versión nueva: comparación, respuesta de GitHub, errores de red |
| `test_theme.py` | paletas, fuentes, escala, formas redondeadas, iconos y el icono de la app |
| `test_job_presenters.py`, `test_view_presenters.py` | textos de las filas de la cola y de la vista PS5 |
| `test_make_icon.py` | generación de `assets/icon.png` y `assets/icon.ico` |
| `test_code_standards.py` | que el repositorio cumpla las rules y que el verificador detecte cada violación |

La UI de Tkinter no tiene tests automáticos: por eso toda la lógica de texto
vive en funciones puras (`ui/presenters.py`, `ui/job_presenters.py`,
`ui/explorer/*presenters.py`) y toda la lógica de negocio en `services/`,
testeables sin pantalla.

`ConversionRunner` acepta un `process_factory`; los tests lo sustituyen por un
`FakeProcess` para no depender de MkPFS ni de juegos reales. Del mismo modo, los
servicios de la vista PS5 reciben un `client_factory` o `session_factory`: los
tests usan un servidor FTP local con `pyftpdlib` (fixture `ftp_server` de
`conftest.py`) y una sesión AVA1 simulada, así que no hace falta una PS5.

## Multiplataforma

- Todo lo que depende del sistema operativo vive en `infrastructure/` y se
  decide en funciones puras que reciben la plataforma como parámetro, para
  testear las ramas de Windows desde Linux.
- Los scripts `.bat` y `.ps1` se guardan con finales de línea CRLF
  (`.gitattributes`); `instalar.ps1` lleva BOM UTF-8 para que PowerShell 5.1
  muestre bien las tildes. Los `.bat` evitan tildes por la codificación de `cmd`.
- Antes de publicar un cambio en la instalación o en procesos, pruébalo en
  Windows real.

## Flujo de Git

- Rama principal: `main` (siempre estable).
- Ramas de trabajo: `feat/…`, `fix/…`, `refactor/…`, `docs/…`.
- Mensajes con [Conventional Commits](https://www.conventionalcommits.org/es/):
  `feat: estimación por idioma`, `fix(estimator): …`.
- Cada cambio visible para el usuario se anota en [`CHANGELOG.md`](../CHANGELOG.md).

## Publicar una versión

1. Sube `__version__` en `src/ffpfsc_converter/__init__.py` (SemVer) y la insignia
   de versión del `README.md`.
2. Mueve las entradas de *Sin publicar* a la nueva versión en `CHANGELOG.md`.
3. `git commit -m "chore(release): v1.x.y" && git tag v1.x.y && git push --follow-tags`.
4. Publica la *Release* en GitHub con las notas de esa versión del CHANGELOG:

   ```bash
   gh release create v1.x.y --title "v1.x.y" --notes-file notas.md
   ```

   Es lo que activa el aviso **Actualizar a v1.x.y** en las apps instaladas: la app
   consulta `releases/latest` de la API de GitHub (sin credenciales) y compara con
   su `__version__`. Los borradores y las *pre-releases* no se anuncian.

Si cambia el diseño del icono (`ui/theme/app_icon.py`), regenera los archivos de
los accesos directos con `python tools/make_icon.py` y versiona `assets/`.

## Rules de Claude Code

Normas obligatorias en [`.claude/rules/`](../.claude/rules/) (Claude Code las carga
siempre):

| Rule | Norma |
|------|-------|
| `documentacion.md` | Español neutro; docstrings con descripción breve, `Args`, `Returns` y `Raises`. |
| `limite-de-lineas.md` | Ningún archivo supera 250 líneas; cómo modularizar. |
| `codigo-limpio.md` | Nombres, funciones, tipos, errores, sin números mágicos. |
| `buenas-practicas.md` | Capas, hilos, MkPFS, datos del usuario, tests, Git, definición de terminado. |

## Skills de Claude Code

En [`.claude/skills/`](../.claude/skills/) hay tres skills que estandarizan el
trabajo en este repositorio (Claude Code las carga automáticamente):

| Skill | Para qué |
|-------|----------|
| `ffpfsc-architecture` | Dónde va cada cosa y qué puede importar cada capa. |
| `ffpfsc-clean-code` | Nombres, tamaño de funciones, tipos, docstrings, errores. |
| `ffpfsc-best-practices` | Hilos + Tkinter, MkPFS, tests, commits y checklist final. |
