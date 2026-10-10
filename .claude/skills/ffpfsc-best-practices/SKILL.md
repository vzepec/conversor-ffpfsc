---
name: ffpfsc-best-practices
description: Buenas prácticas del Conversor FFPFSC — hilos y Tkinter, integración con MkPFS, seguridad de los datos del usuario, testing, Git/versionado y checklist obligatorio antes de dar un cambio por terminado. Úsala al implementar o revisar funcionalidades, al tocar la conversión o la UI, y antes de commitear.
---

# Buenas prácticas del Conversor FFPFSC

## 1. Hilos y Tkinter

- **Solo el hilo principal toca widgets.** Desde un hilo de fondo, publica un
  evento (`domain/events.py`); nunca llames a `tree.set`, `messagebox`, etc.
- Los hilos de trabajo son `daemon=True` para no bloquear el cierre.
- Estado compartido entre hilos: asignaciones simples o `threading.Event`.
  Si necesitas algo más complejo, usa un `Lock` y documéntalo.
- Operaciones largas (leer el juego, estimar, convertir) **siempre** fuera del
  hilo de la UI. Si algo tarda > 100 ms, va a un servicio en segundo plano.

## 2. MkPFS

- Todo el conocimiento de MkPFS vive en `infrastructure/mkpfs_adapter.py`.
- El backend de compresión es **siempre `zlib-ng`** (`COMPRESSION_BACKEND`).
  No lo cambies sin verificar en consola: `isal` produce imágenes que la PS5
  lee mal (MkPFS #132).
- Se ejecuta como subproceso con `sys.executable -m mkpfs` para usar el mismo
  entorno virtual, en sesión propia (`start_new_session=True`) para poder
  cancelar con `killpg`.
- Al añadir un flag: verifica que existe con `python -m mkpfs pack folder -h`
  y añade un test en `tests/test_mkpfs_adapter.py`.
- Si actualizas MkPFS, revisa que el formato de progreso (`[n/m] 37% fase @ X MB/s`)
  siga coincidiendo con `parse_progress`.

## 3. Proteger los datos del usuario

Los juegos ocupan decenas de GB y tardan horas en copiarse:

- **Nunca** modifiques ni borres el origen.
- Pide confirmación antes de sobrescribir un `.ffpfsc` existente.
- Si la conversión falla o se cancela, borra la salida parcial (`remove_quietly`).
- Comprueba el espacio libre antes de empezar (`services/preflight.py`).
- Los archivos temporales van a la carpeta de destino, no a `/tmp`.

## 4. Tests

- Cada función de `services/`, `infrastructure/` y `ui/presenters.py` nueva o
  modificada lleva test en `tests/test_<módulo>.py`.
- Usa `tmp_path` y la fixture `game_folder` de `conftest.py`; nunca juegos reales
  ni rutas absolutas del equipo.
- Sustituye procesos con dobles (`FakeProcess`) a través de la inyección de
  dependencias; `monkeypatch` solo para casos puntuales.
- Un bug corregido = un test que lo reproduce primero.
- La UI (`ui/app.py`) no se testea automáticamente: mantenla delgada. Si una
  lógica de la UI merece un test, es señal de que debe moverse a `presenters.py`
  o a un servicio.

## 5. Git y versiones

- Ramas: `feat/…`, `fix/…`, `refactor/…`, `docs/…`; `main` siempre estable.
- Commits pequeños con [Conventional Commits](https://www.conventionalcommits.org/es/).
- Nunca se versionan juegos ni imágenes (`*.ffpfsc`, `*.exfat`, `*.ffpkg`, `*.pkg`)
  ni `.venv/` — ya están en `.gitignore`.
- Cambios visibles → entrada en `CHANGELOG.md` bajo *Sin publicar*.
- Versión en `src/ffpfsc_converter/__init__.py` siguiendo SemVer.

## 6. Dependencias

- Dependencias de ejecución en `[project.dependencies]`, de desarrollo en
  `[project.optional-dependencies].dev` de `pyproject.toml`.
- Antes de añadir una dependencia nueva, justifica por qué la stdlib no basta.
- Las dependencias opcionales (como `tkinterdnd2`) se cargan con `try/except`
  y la app debe funcionar sin ellas.

## 7. Checklist antes de dar un cambio por terminado

```bash
source .venv/bin/activate
ruff check src tests      # sin errores
pytest                    # todo en verde
```

- [ ] Las reglas de importación de la skill `ffpfsc-architecture` se cumplen.
- [ ] El código sigue `ffpfsc-clean-code` (tipos, nombres, sin números mágicos).
- [ ] Hay tests para la lógica nueva.
- [ ] Si cambió la UI, se probó a mano con `./abrir.sh` (agregar, estimar, convertir, cancelar).
- [ ] Si cambió la conversión, se convirtió un juego real o de prueba con `--verify`.
- [ ] `CHANGELOG.md` y `docs/` actualizados si aplica.
