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
| Lint | `ruff check src tests` |
| Lint con arreglos automáticos | `ruff check src tests --fix` |

Antes de cada commit: **`ruff check src tests && pytest`** debe pasar.

## Tests

| Archivo | Cubre |
|---------|-------|
| `test_discovery.py` | búsqueda de `eboot.bin`/imágenes, errores, ruta de salida |
| `test_metadata.py` | parseo de `param.json`, idiomas, *best effort* |
| `test_estimator.py` | estimación determinista, datos compresibles e incompresibles |
| `test_mkpfs_adapter.py` | comando `mkpfs pack`, parseo de progreso, corte de líneas `\r`/`\n` |
| `test_conversion.py` | cola, fallo, cancelación y error al lanzar (con `FakeProcess`) |
| `test_presenters.py` | todos los textos que ve el usuario |

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

## Skills de Claude Code

En [`.claude/skills/`](../.claude/skills/) hay tres skills que estandarizan el
trabajo en este repositorio (Claude Code las carga automáticamente):

| Skill | Para qué |
|-------|----------|
| `ffpfsc-architecture` | Dónde va cada cosa y qué puede importar cada capa. |
| `ffpfsc-clean-code` | Nombres, tamaño de funciones, tipos, docstrings, errores. |
| `ffpfsc-best-practices` | Hilos + Tkinter, MkPFS, tests, commits y checklist final. |
