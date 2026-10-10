# Regla: ningún archivo supera las 250 líneas

**Ningún archivo versionado (`.py`, `.md`, `.sh`, `.toml`) puede superar las
250 líneas.** Si un cambio lo haría crecer por encima, se **modulariza en el
mismo cambio**; no se deja para después. La verifica
`python tools/check_standards.py` (también se ejecuta dentro de `pytest`).

## Cómo modularizar

Divide por **responsabilidad**, nunca por "parte 1 / parte 2":

| Si el archivo… | Haz esto |
|----------------|----------|
| Mezcla construcción de widgets con lógica de acciones | Separa la vista (`ui/main_view.py`) del controlador (`ui/app.py`). |
| Agrupa varias operaciones sobre un mismo sistema externo | Conviértelo en subpaquete (`infrastructure/mkpfs_adapter/` con `command.py`, `output.py`, `process.py`…) y reexporta la API pública en `__init__.py`. |
| Tiene muchos diálogos o mensajes | Extráelos a un módulo propio (`ui/dialogs.py`). |
| Tiene muchas funciones auxiliares privadas | Muévelas a un módulo `_<tema>.py` del mismo paquete. |
| Es un test largo | Divide por comportamiento: `test_<módulo>_<aspecto>.py`. |
| Es un documento largo | Divide por tema en `docs/` y enlaza desde el índice. |

## Reglas al dividir

- Cada módulo nuevo tiene su docstring de módulo y respeta las capas de la
  skill `ffpfsc-architecture`.
- Mantén la API pública estable: si mueves una función usada desde otras
  capas, reexpórtala desde el módulo original o actualiza todos los imports.
- Sin importaciones circulares: si dos módulos se necesitan mutuamente, extrae
  lo común a un tercero.
- Actualiza el árbol de `docs/ARCHITECTURE.md`.

## Límites orientativos dentro de un archivo

- Función o método: ≤ 30 líneas de código (sin contar la docstring).
- Clase: una sola responsabilidad; si necesita comentarios de sección
  (`# ---- acciones`, `# ---- eventos`), probablemente son dos clases.
