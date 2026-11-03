"""
tests/unit/test_no_late_local_imports.py

A function that imports a name locally treats it as local to the WHOLE function, so a use above the import raises UnboundLocalError (a real case lost two subsequent values this way).
this way, hidden by an `except Exception`). scripts/find_late_local_imports.py finds the pattern; this test runs it over the repo so it cannot come back.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("find_late_local_imports", ROOT / "scripts" / "find_late_local_imports.py")
_scanner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_scanner)
scan = _scanner.scan_source


def test_finds_a_use_before_the_local_import():
    src = "def f():\n    use(Thing)\n    from m import Thing\n"
    assert [(h[1], h[2], h[3], h[4]) for h in scan(src)] == [("f", "Thing", 2, 3)]


def test_an_import_before_the_use_is_fine():
    assert scan("def f():\n    from m import Thing\n    use(Thing)\n") == []


def test_a_parameter_or_an_earlier_assignment_is_already_bound():
    assert scan("def f(Thing=None):\n    if Thing is None:\n        from m import make as Thing\n") == []
    assert scan("def f():\n    for Thing in xs:\n        use(Thing)\n    from m import Thing\n") == []


def test_a_nested_function_has_its_own_scope():
    src = "def f():\n    def g():\n        return Thing\n    from m import Thing\n"
    assert scan(src) == []                                            # g reads the enclosing Thing; f itself uses it only after the import


def test_the_app_has_no_late_local_imports():
    hits = []
    for p in sorted((ROOT / "app").rglob("*.py")):
        hits += scan(p.read_text(encoding="utf8"), str(p.relative_to(ROOT)))
    assert hits == [], "\n".join(f"{f}:{use}: {fn}() uses '{name}' before its local import at line {imp}" for f, fn, name, use, imp in hits)
