# Regla: código limpio

Aplica a todo el código Python de `src/`, `tools/` y `tests/`.

## Nombres

- Identificadores en **inglés**; documentación y textos en **español neutro**
  (ver `documentacion.md`).
- Funciones = verbo + objeto: `find_game_root`, `build_pack_command`.
- Booleanos con `is_` / `has_` / `can_`: `is_queued`, `HAS_DND`.
- Sin abreviaturas crípticas; nombres de una letra solo en comprensiones cortas.
- `_prefijo` para todo lo que no se usa fuera del módulo o la clase.
- Constantes en `MAYÚSCULAS`: de negocio en `config.py`, visuales en `ui/theme.py`.

## Funciones

- Una sola responsabilidad y ≤ 30 líneas de código.
- Máximo 4 parámetros; si hay más, agrúpalos en una `dataclass`.
- Retorno temprano en lugar de `if` anidados.
- Prefiere funciones puras; la E/S y los efectos secundarios van en los bordes
  (capa `infrastructure`).
- No mutes argumentos salvo que sea el propósito documentado de la función.

## Tipos

- `from __future__ import annotations` en todos los módulos.
- Firmas completamente tipadas, incluido `-> None`.
- `X | None`, `list[str]`, `dict[str, int]` (sintaxis moderna).
- Parámetros con tipos abstractos (`Sequence`, `Iterable`, `Mapping`);
  retornos con tipos concretos.
- Valores inmutables con `@dataclass(frozen=True)`; estados con `Enum`.
- Prohibido pasar tuplas o diccionarios con significado posicional entre
  módulos: crea una `dataclass`.
- Contratos para dobles de test con `typing.Protocol`.

## Errores

- Errores esperables del usuario: subclase de `ConverterError` (`errors.py`)
  con mensaje listo para mostrar en español neutro.
- Captura la excepción más específica posible.
- `except Exception` solo en funciones *best effort* documentadas, con
  `# noqa: BLE001 - motivo`.
- Ignorar un error a propósito: `contextlib.suppress(TipoDeError)`, nunca
  `except: pass`.

## Sin magia

- Ningún número ni cadena de negocio literal fuera de `config.py`.
- Un texto que aparece dos veces se convierte en constante o en función de
  `ui/presenters.py`.

## Estilo

- `ruff check src tests tools` sin errores (configuración en `pyproject.toml`,
  línea de 100 caracteres).
- Imports absolutos (`from ffpfsc_converter.x import y`), ordenados por ruff.
- Imports diferidos solo para dependencias opcionales o pesadas, con
  comentario que lo justifique.
- Archivos ≤ 250 líneas (ver `limite-de-lineas.md`).
