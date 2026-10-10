# Regla: buenas prácticas

## Arquitectura

- Respeta las capas `domain → infrastructure → services → ui`: las
  dependencias solo apuntan hacia abajo (detalle en la skill
  `ffpfsc-architecture` y en `docs/ARCHITECTURE.md`).
- Todo lo que lanza procesos o depende del entorno se **inyecta** (parámetro
  con valor por defecto real) para poder sustituirlo en los tests.

## Hilos y Tkinter

- Solo el hilo principal toca widgets. Los hilos de fondo publican eventos de
  `domain/events.py` a través de un `EventSink`.
- Cualquier operación de más de ~100 ms (leer el juego, estimar, convertir)
  se ejecuta fuera del hilo de la interfaz.
- Hilos de trabajo con `daemon=True`; cancelación con `threading.Event`.

## MkPFS

- Todo el conocimiento de MkPFS vive en `infrastructure/mkpfs_adapter/`.
- Backend de compresión siempre `zlib-ng` (`isal` genera imágenes que la PS5
  lee mal, MkPFS #132).
- Cada flag nuevo se comprueba con `python -m mkpfs pack folder -h` y lleva test.

## Datos del usuario

- Nunca se modifica ni se borra el origen.
- Confirmación antes de sobrescribir un `.ffpfsc`.
- La salida parcial se borra si la conversión falla o se cancela.
- Se comprueba el espacio libre antes de empezar.
- Los temporales van a la carpeta de destino, no a `/tmp`.

## Tests

- Toda lógica nueva o modificada de `services/`, `infrastructure/`,
  `ui/presenters.py` y `tools/` lleva test.
- Un bug corregido = primero un test que lo reproduce.
- Usa `tmp_path` y las fixtures de `conftest.py`; nunca juegos reales ni rutas
  absolutas del equipo.
- `ui/app.py` y `ui/main_view.py` se mantienen delgados; la lógica que merezca
  test se mueve a `presenters.py` o a un servicio.

## Git

- Ramas `feat/…`, `fix/…`, `refactor/…`, `docs/…`; `main` siempre estable.
- Commits pequeños con Conventional Commits.
- Nunca se versionan juegos ni imágenes (`*.ffpfsc`, `*.exfat`, `*.ffpkg`,
  `*.pkg`) ni `.venv/`.
- Cambios visibles para el usuario → `CHANGELOG.md` en *Sin publicar*.

## Definición de terminado

Un cambio está terminado solo cuando:

```bash
.venv/bin/ruff check src tests tools
.venv/bin/python tools/check_standards.py
.venv/bin/python -m pytest
```

pasan sin errores y, si tocó la interfaz o la conversión, se probó a mano con
`./abrir.sh`.
