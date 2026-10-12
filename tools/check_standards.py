"""Verifica los estándares del repositorio definidos en ``.claude/rules/``.

Comprueba dos cosas:

1. Ningún archivo de texto versionado supera ``MAX_LINES`` líneas.
2. Toda función y método tiene docstring. En ``src/`` y ``tools/`` la docstring
   debe incluir las secciones ``Args``, ``Returns``, ``Yields`` y ``Raises``
   cuando correspondan; en ``tests/`` basta la descripción breve.

Uso: ``python tools/check_standards.py`` (código de salida 1 si hay violaciones).
"""
from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterator
from pathlib import Path

MAX_LINES = 250
CHECKED_SUFFIXES = frozenset({".py", ".md", ".sh", ".toml", ".ps1", ".bat"})
EXCLUDED_DIRS = frozenset({
    ".git", ".venv", "third_party", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist",
})
FULL_DOC_DIRS = ("src", "tools")
BRIEF_DOC_DIRS = ("tests",)
_IGNORED_PARAMS = frozenset({"self", "cls"})
_SECTION_RE = re.compile(r"^(\w+):\s*$")
_ITERATOR_ANNOTATIONS = ("Iterator", "Iterable", "Generator", "AsyncIterator")
_ARG_RE = re.compile(r"^\s{4}\*{0,2}(\w+)\s*\(")

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def iter_text_files(root: Path) -> Iterator[Path]:
    """Recorre los archivos de texto del repositorio que deben verificarse.

    Args:
        root (Path): Raíz del repositorio.

    Yields:
        Path: Cada archivo con extensión verificable fuera de carpetas excluidas.
    """
    for path in sorted(root.rglob("*")):
        rel_parts = path.relative_to(root).parts
        if any(p in EXCLUDED_DIRS or p.endswith(".egg-info") for p in rel_parts):
            continue
        if path.is_file() and path.suffix in CHECKED_SUFFIXES:
            yield path


def check_line_limit(path: Path, root: Path) -> list[str]:
    """Comprueba que un archivo no supere el límite de líneas.

    Args:
        path (Path): Archivo a verificar.
        root (Path): Raíz del repositorio, para mostrar rutas relativas.

    Returns:
        list[str]: Una violación si el archivo es demasiado largo; vacía si cumple.
    """
    count = len(path.read_text(encoding="utf-8-sig").splitlines())
    if count <= MAX_LINES:
        return []
    return [f"{path.relative_to(root)}: {count} líneas (máximo {MAX_LINES}); modularízalo"]


def check_docstrings(path: Path, root: Path, full: bool) -> list[str]:
    """Comprueba la documentación de todas las funciones y métodos de un módulo.

    Args:
        path (Path): Archivo Python a analizar.
        root (Path): Raíz del repositorio, para mostrar rutas relativas.
        full (bool): ``True`` exige las secciones Args/Returns/Yields/Raises.

    Returns:
        list[str]: Violaciones encontradas, con ruta y número de línea.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel = path.relative_to(root)
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        doc = ast.get_docstring(node)
        where = f"{rel}:{node.lineno} {node.name}"
        if not doc:
            problems.append(f"{where}: falta la docstring")
        elif full and not isinstance(node, ast.ClassDef):
            problems += [f"{where}: {msg}" for msg in _missing_sections(node, doc)]
    return problems


def _missing_sections(node: FunctionNode, doc: str) -> list[str]:
    """Lista las secciones obligatorias ausentes en la docstring de una función.

    Args:
        node (FunctionNode): Nodo AST de la función.
        doc (str): Docstring de la función.

    Returns:
        list[str]: Descripción de cada sección o parámetro que falta.
    """
    sections = _parse_sections(doc)
    problems: list[str] = []
    documented_args = {
        m.group(1) for line in sections.get("Args", []) if (m := _ARG_RE.match(line))
    }
    for param in _param_names(node):
        if param not in documented_args:
            problems.append(f"falta el parámetro '{param}' en Args")
    body = list(_own_scope_nodes(node))
    if _is_generator(node, body):
        if "Yields" not in sections:
            problems.append("falta la sección Yields")
    elif _returns_value(node, body) and "Returns" not in sections:
        problems.append("falta la sección Returns")
    if any(isinstance(n, ast.Raise) for n in body) and "Raises" not in sections:
        problems.append("falta la sección Raises")
    return problems


def _parse_sections(doc: str) -> dict[str, list[str]]:
    """Divide una docstring estilo Google en sus secciones.

    Args:
        doc (str): Docstring ya normalizada por ``ast.get_docstring``.

    Returns:
        dict[str, list[str]]: Nombre de sección → líneas que contiene.
    """
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in doc.splitlines():
        match = _SECTION_RE.match(line)
        if match:
            current = sections.setdefault(match.group(1), [])
        elif current is not None:
            current.append(line)
    return sections


def _param_names(node: FunctionNode) -> list[str]:
    """Obtiene los nombres de parámetros que deben documentarse.

    Args:
        node (FunctionNode): Nodo AST de la función.

    Returns:
        list[str]: Parámetros sin ``self`` ni ``cls``, incluidos ``*args`` y ``**kwargs``.
    """
    args = node.args
    names = [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    names += [a.arg for a in (args.vararg, args.kwarg) if a is not None]
    return [n for n in names if n not in _IGNORED_PARAMS]


def _own_scope_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Recorre los nodos del cuerpo sin entrar en funciones, lambdas ni clases anidadas.

    Args:
        node (ast.AST): Nodo de la función a recorrer.

    Yields:
        ast.AST: Cada nodo que pertenece al ámbito propio de la función.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        yield child
        yield from _own_scope_nodes(child)


def _is_stub(node: FunctionNode) -> bool:
    """Indica si la función es un stub (solo docstring y ``...``), como en un ``Protocol``.

    Args:
        node (FunctionNode): Nodo AST de la función.

    Returns:
        bool: ``True`` si el cuerpo solo contiene expresiones.
    """
    return all(isinstance(s, ast.Expr) for s in node.body)


def _is_generator(node: FunctionNode, body: list[ast.AST]) -> bool:
    """Indica si la función produce valores con ``yield`` o es un stub que devuelve un iterador.

    Args:
        node (FunctionNode): Nodo AST de la función.
        body (list[ast.AST]): Nodos del ámbito propio de la función.

    Returns:
        bool: ``True`` si debe documentarse con ``Yields``.
    """
    if any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in body):
        return True
    annotation = ast.unparse(node.returns) if node.returns else ""
    return _is_stub(node) and annotation.startswith(_ITERATOR_ANNOTATIONS)


def _returns_value(node: FunctionNode, body: list[ast.AST]) -> bool:
    """Indica si la función devuelve un valor distinto de ``None``.

    Args:
        node (FunctionNode): Nodo AST de la función.
        body (list[ast.AST]): Nodos del ámbito propio de la función.

    Returns:
        bool: ``True`` si hay un ``return`` con valor o es un stub con retorno anotado.
    """
    if any(isinstance(n, ast.Return) and n.value is not None for n in body):
        return True
    annotation = ast.unparse(node.returns) if node.returns else "None"
    return _is_stub(node) and annotation != "None"


def run(root: Path) -> list[str]:
    """Ejecuta todas las verificaciones sobre el repositorio.

    Args:
        root (Path): Raíz del repositorio.

    Returns:
        list[str]: Todas las violaciones encontradas; vacía si el repositorio cumple.
    """
    problems: list[str] = []
    for path in iter_text_files(root):
        problems += check_line_limit(path, root)
        top = path.relative_to(root).parts[0]
        if path.suffix == ".py" and top in FULL_DOC_DIRS + BRIEF_DOC_DIRS:
            problems += check_docstrings(path, root, full=top in FULL_DOC_DIRS)
    return problems


def main() -> int:
    """Punto de entrada de línea de comandos.

    Returns:
        int: ``0`` si no hay violaciones, ``1`` en caso contrario.
    """
    problems = run(Path(__file__).resolve().parent.parent)
    for problem in problems:
        print(problem)
    print(f"{len(problems)} violaciones" if problems else "Estándares OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
