import asyncio
from types import SimpleNamespace

import app.file_tools_attach  # noqa: F401  (attaches the extracted methods)
from app.file_tools import FileToolTurn, normalize_flags
from app.file_tools_keys import exact_variant


def test_exact_variant_is_strict():
    known = {"reads", "greps", "globs"}
    assert exact_variant("reads_file", known) == "reads"
    assert exact_variant("reads_path", known) is None
    assert exact_variant("unknown", known) is None


def test_normalize_flags_clamps_and_drops():
    flags, ignored = normalize_flags({"reads_file": [{"path": "a.py", "limit": 99999}], "bogus": 1, "globs": None}, ("reads", "greps", "globs"))
    assert flags["reads"] == [{"path": "a.py", "limit": 1000}]
    assert any(i.startswith("normalised") for i in ignored) and any(i.startswith("ignored") for i in ignored)


def test_read_and_glob_under_budget():
    rows = [SimpleNamespace(path="src/a.py", code="x = 1\ny = 2\n", status="done", module="m"), SimpleNamespace(path="src/b.txt", code="hello", status="done", module="m")]

    async def provider():
        return rows
    turn = FileToolTurn(provider)
    out = asyncio.run(turn.run_round({"reads": [{"path": "src/a.py"}], "globs": [{"pattern": "src/*.py"}]}, 1))
    assert [r["tool"] for r in out] == ["globs", "reads"]
    assert out[1]["payload"]["content"].startswith("x = 1")
    err = asyncio.run(turn.run_round({"reads": [{"path": "../etc/passwd"}]}, 2))
    assert err[0]["status"] == "error"
