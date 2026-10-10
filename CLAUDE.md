# Conversor FFPFSC

Interfaz gráfica (Tkinter) sobre MkPFS para convertir juegos de PS5 (carpeta,
`.exfat`, `.ffpkg`) a `.ffpfsc`. Código en `src/ffpfsc_converter/`.

## Comandos

- Ejecutar: `./abrir.sh` o `PYTHONPATH=src .venv/bin/python -m ffpfsc_converter`
- Tests: `.venv/bin/python -m pytest`
- Lint: `.venv/bin/ruff check src tests`
- Entorno de desarrollo: `./instalar.sh --dev`

## Reglas

Sigue siempre las skills del proyecto:

- `ffpfsc-architecture` — capas `domain → infrastructure → services → ui`, qué puede importar cada una.
- `ffpfsc-clean-code` — identificadores en inglés, docstrings/UI en español, tipado completo, constantes en `config.py`.
- `ffpfsc-best-practices` — hilos y Tkinter, MkPFS (siempre `zlib-ng`), proteger datos del usuario, tests, checklist.

Un cambio no está terminado hasta que `ruff check src tests` y `pytest` pasan.
Documentación de fondo: `docs/ARCHITECTURE.md`.
