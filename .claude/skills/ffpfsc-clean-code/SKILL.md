---
name: ffpfsc-clean-code
description: Estándar de código limpio del Conversor FFPFSC — idioma, nombres, tamaño de funciones, tipado, docstrings, constantes y manejo de errores. Úsala al escribir, revisar o refactorizar cualquier código Python del repositorio.
---

# Código limpio en el Conversor FFPFSC

## Idioma

| Elemento | Idioma | Ejemplo |
|----------|--------|---------|
| Identificadores (variables, funciones, clases, módulos) | **inglés** | `estimate_sizes`, `ConversionJob` |
| Docstrings y comentarios | **español** | `"""Estima el tamaño final…"""` |
| Textos de la UI y mensajes de error | **español** | `"No encontré un juego dentro de…"` |
| Mensajes de commit | español o inglés, Conventional Commits | `feat: …` |

## Nombres

- Funciones = verbo + objeto: `find_game_root`, `build_pack_command`, `read_game_info`.
- Booleanos con `is_`/`has_`/`can_`: `is_queued`, `is_enough`, `HAS_DND`.
- Sin abreviaturas crípticas (`job`, no `j`, salvo en comprensiones cortas).
- Privado con `_` inicial; lo que no se usa fuera del módulo, es privado.
- Constantes en `MAYÚSCULAS`, en `config.py` (negocio) o `ui/theme.py` (visual).

## Funciones

- **Una responsabilidad**, idealmente < 30 líneas. Si necesitas un comentario
  de sección dentro de una función, extrae una función.
- Máximo ~4 parámetros; si hay más, agrúpalos en una `dataclass` (ver `ConversionOptions`).
- Prefiere funciones **puras** (entrada → salida) y deja la E/S en los bordes.
- Retorno temprano en lugar de `if` anidados.
- No mutar argumentos salvo que sea el propósito explícito (como `analyze_job`)
  y esté documentado.

## Tipado

- `from __future__ import annotations` en todos los módulos.
- Firmas públicas **completamente tipadas**, incluido `-> None`.
- `X | None` en lugar de `Optional[X]`; `list[str]` en lugar de `List[str]`.
- Colecciones abstractas en parámetros (`Sequence`, `Iterable`), concretas en retornos.
- Valores inmutables como `@dataclass(frozen=True)`; estados como `Enum`.
- Nada de tuplas posicionales con significado (`("done", job, ok, msg)`) → dataclass.
- Para dobles de test, define un `Protocol` (ver `ProcessHandle`).

## Docstrings y comentarios

- Docstring de una línea en toda función/clase pública que no sea obvia.
- Documenta el **porqué**, no el qué: `# isal genera bloques que la PS5 lee mal (#132)`.
- `Raises:` en el docstring si la función lanza excepciones de dominio.
- No dejes código comentado ni `print` de depuración.

## Errores

- Errores esperables del usuario → subclase de `ConverterError` con mensaje listo
  para mostrar. La UI hace `messagebox.showerror(APP_TITLE, str(exc))`.
- Captura la excepción **más específica** posible. `except Exception` solo en
  funciones *best effort* documentadas como tales, con `# noqa: BLE001 - motivo`.
- Nunca `except: pass` silencioso; usa `contextlib.suppress(OSError)` cuando
  ignorar sea intencional.
- No uses excepciones para control de flujo normal.

## Constantes y magia

- Ningún número de negocio en el código: `PFSC_BLOCK_SIZE`, no `65536`.
- Ninguna cadena repetida: si un texto aparece dos veces, constante en el módulo
  o función en `presenters.py`.

## Estilo

- `ruff check src tests` sin errores (configuración en `pyproject.toml`, línea de 100).
- Imports ordenados por ruff (`I`): stdlib, terceros, proyecto; absolutos
  (`from ffpfsc_converter.x import y`).
- Imports diferidos solo para dependencias opcionales o pesadas (`mkpfs`,
  `tkinter` en `__main__`), con comentario si no es evidente.

## Antes / después

```python
# ✗ Antes
self.events.put(("done", job, rc == 0, f"código {rc}", time.time() - t0))

# ✓ Después
self._emit(JobFinished(job, ConversionResult(
    succeeded=succeeded, cancelled=cancelled,
    elapsed_seconds=time.monotonic() - started, message=f"código {return_code}",
)))
```
