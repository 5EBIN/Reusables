"""Find the UnboundLocalError pattern: a function that imports a name locally (so Python treats the name as local to the WHOLE function) and uses that name on an
earlier line than the import. Such a use raises UnboundLocalError at run time; in this repo the error was being swallowed by `except Exception`.

usage (cwd backend): venv/Scripts/python.exe scripts/find_late_local_imports.py [path ...]     (default: app)
Exit code 1 when anything is found.
"""
import ast
import sys
from pathlib import Path


def _own_nodes(fn):
    """Every node of `fn`'s own scope: descends into blocks, not into nested functions / classes / lambdas (they have their own scope)."""
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def scan_source(source: str, filename: str = "<src>") -> list:
    """[(file, function, name, use_line, first_import_line)] for every late use."""
    hits = []
    tree = ast.parse(source, filename)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first_import: dict = {}
        uses: dict = {}
        bound: dict = {}        # name -> lines where it is bound some other way (assignment, loop target, with/except name); parameters are bound at line 0
        args = fn.args
        for a in [*args.posonlyargs, *args.args, *args.kwonlyargs, *([args.vararg] if args.vararg else []), *([args.kwarg] if args.kwarg else [])]:
            bound.setdefault(a.arg, []).append(0)
        for node in _own_nodes(fn):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = (alias.asname or alias.name).split(".")[0]
                    first_import[name] = min(first_import.get(name, node.lineno), node.lineno)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                uses.setdefault(node.id, []).append(node.lineno)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                bound.setdefault(node.id, []).append(node.lineno)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bound.setdefault(node.name, []).append(node.lineno)
        for name, line in first_import.items():
            early = [u for u in uses.get(name, []) if u < line and not any(b <= u for b in bound.get(name, []))]
            if early:
                hits.append((filename, fn.name, name, min(early), line))
    return hits


def main(paths):
    hits = []
    for root in paths:
        for p in sorted(Path(root).rglob("*.py")) if Path(root).is_dir() else [Path(root)]:
            try:
                hits += scan_source(p.read_text(encoding="utf8"), str(p))
            except SyntaxError as exc:
                print(f"skip {p}: {exc}", file=sys.stderr)
    for f, fn, name, use, imp in hits:
        print(f"{f}:{use}: {fn}() uses '{name}' before its local import at line {imp}")
    print(f"{len(hits)} hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["app"]))
