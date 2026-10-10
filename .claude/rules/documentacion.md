# Regla: documentación

Obligatoria en todo el repositorio. La verifica `python tools/check_standards.py`
(también se ejecuta dentro de `pytest`).

## 1. Idioma: español neutro

Toda la documentación (docstrings, comentarios, archivos `.md`, textos de la UI,
mensajes de error) se escribe en **español neutro**:

- Tuteo (`elige`, `arrastra`), nunca voseo (`elegí`, `arrastrá`).
- Sin regionalismos: usa `equipo` (no *computadora*/*ordenador*), `archivo`
  (no *fichero*), `carpeta`, `guardar`, `hacer clic`.
- Sin anglicismos innecesarios cuando existe un término común en español:
  `registro` (no *log* en textos), `cola`, `tarea`. Se mantienen los nombres
  técnicos propios: *thread*/hilo, PFS, exFAT, MkPFS.
- Ortografía completa: tildes, `¿?`, `¡!`.

Los **identificadores** (variables, funciones, clases, módulos) van en inglés.

## 2. Docstrings de funciones y métodos

**Toda** función y método (públicos, privados, anidados, `__init__`,
propiedades y métodos de `Protocol`) en `src/` y `tools/` lleva una docstring
estilo Google con este orden:

1. **Descripción breve**: una sola línea, en modo indicativo, que resume el
   propósito (`Busca…`, `Calcula…`, `Devuelve…`). Termina en punto.
2. **`Args:`** cada parámetro (excepto `self`/`cls`) como
   `nombre (tipo): descripción.` Se omite si no hay parámetros.
3. **`Returns:`** `tipo: explicación de lo que devuelve.` Se omite si devuelve `None`.
   En generadores se usa **`Yields:`** con el mismo formato.
4. **`Raises:`** `TipoDeError: condición en la que se lanza.` Incluye también
   los errores de dominio que la función **propaga** a propósito. Se omite si
   no lanza nada.

Opcionalmente, entre la línea breve y `Args:`, un párrafo con el **porqué**
(decisiones, restricciones de la PS5 o de MkPFS).

```python
def resolve_game_root(path: Path) -> Path:
    """Determina qué debe empaquetarse a partir de la ruta agregada.

    Args:
        path (Path): Carpeta o imagen que agregó el usuario.

    Returns:
        Path: Carpeta que contiene ``eboot.bin`` o imagen ``.exfat``/``.ffpkg``.

    Raises:
        SourceNotFoundError: Si la ruta no existe.
        UnsupportedFormatError: Si es un archivo que no es una imagen soportada.
        GameNotFoundError: Si es una carpeta sin un juego reconocible.
    """
```

## 3. Clases y módulos

- Todo **módulo** empieza con una docstring que explica su responsabilidad.
- Toda **clase** tiene docstring con descripción breve; las `dataclass` y
  clases con estado público documentan sus campos en **`Attributes:`** con el
  formato `nombre (tipo): descripción.`

## 4. Tests

En `tests/` cada función lleva al menos la **descripción breve** que explica
qué comportamiento verifica (`"""Ignora carpetas más profundas que el límite."""`).
No hace falta `Args` para fixtures.

## 5. Comentarios

- Explican el **porqué**, nunca repiten el qué.
- Sin código comentado, `TODO` sin dueño ni `print` de depuración.

## 6. Documentación del proyecto

Si un cambio altera la estructura, el uso o una decisión técnica, actualiza en
el mismo commit `README.md`, `docs/*.md` y `CHANGELOG.md`.
