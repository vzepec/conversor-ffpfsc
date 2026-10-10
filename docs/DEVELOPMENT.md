# Desarrollo

## Entorno

```bash
./instalar.sh --dev          # crea .venv e instala el paquete editable + pytest + ruff
source .venv/bin/activate
```

## Comandos

| Tarea | Comando |
|-------|---------|
| Ejecutar la app | `./abrir.sh` o `python -m ffpfsc_converter [rutas…]` |
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
| `test_code_standards.py` | que el repositorio cumpla las rules y que el verificador detecte cada violación |

La UI de Tkinter no tiene tests automáticos: por eso toda la lógica de texto
vive en `ui/presenters.py` y toda la lógica de negocio en `services/`, ambos
100 % testeables sin pantalla.

`ConversionRunner` acepta un `process_factory`; los tests lo sustituyen por un
`FakeProcess` para no depender de MkPFS ni de juegos reales.

## Flujo de Git

- Rama principal: `main` (siempre estable).
- Ramas de trabajo: `feat/…`, `fix/…`, `refactor/…`, `docs/…`.
- Mensajes con [Conventional Commits](https://www.conventionalcommits.org/es/):
  `feat: estimación por idioma`, `fix(estimator): …`.
- Cada cambio visible para el usuario se anota en [`CHANGELOG.md`](../CHANGELOG.md).

## Publicar una versión

1. Sube `__version__` en `src/ffpfsc_converter/__init__.py` (SemVer).
2. Mueve las entradas de *Sin publicar* a la nueva versión en `CHANGELOG.md`.
3. `git commit -m "chore: v1.x.y" && git tag v1.x.y && git push --follow-tags`.

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
