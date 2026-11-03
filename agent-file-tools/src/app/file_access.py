"""Glob, grep and ranged read over an in-memory list of file rows. Pure functions: the host loads the rows (from a database, a checkout, an upload) and passes them in.
Every path or glob a request names goes through `_assert_in_project`, which refuses absolute paths and traversal."""
from __future__ import annotations
import re
import logging
logger = logging.getLogger(__name__)


class ProjectScopeError(Exception):
    """Raised when a requested path escapes the project scope."""


def _assert_in_project(file_path: str) -> None:
    """Reject absolute paths and path-traversal attempts."""
    if file_path.startswith("/") or file_path.startswith("\\"):
        raise ProjectScopeError(f"Absolute paths not allowed: {file_path!r}")
    parts = re.split(r"[/\\]", file_path)
    if ".." in parts:
        raise ProjectScopeError(f"Path traversal not allowed: {file_path!r}")


from dataclasses import dataclass  # noqa: E402

TYPE_EXTENSIONS: dict[str, tuple] = {
    "ts": (".ts", ".tsx"), "js": (".js", ".jsx", ".mjs", ".cjs"), "py": (".py",), "css": (".css",),
    "json": (".json",), "md": (".md",), "prisma": (".prisma",), "sql": (".sql",),
}
GREP_DEFAULT_ITEMS = 50
GREP_MAX_ITEMS = 200
GREP_TEXT_BUDGET = 12_000          # characters of returned text per grep
GREP_LINE_CAP = 300                # characters per returned line (the "…" marker is not counted)
GREP_PATTERN_MAX = 500
GREP_LINE_SCAN_CAP = 2_000         # a line is cut to this many characters BEFORE matching
GREP_SCAN_FILES = 500
GREP_SCAN_CHARS = 2_000_000
GLOB_DEFAULT_LIMIT = 200
GLOB_MAX_LIMIT = 500
READ_DEFAULT_LINES = 400
READ_MAX_LINES = 1_000
LEGACY_READ_CHARS = 8_000          # what tool_read_file has always cut at


@dataclass(frozen=True)
class FileRow:
    path: str
    status: str
    module: str | None
    tag: str | None
    code: str

def rows_listing(rows) -> list[dict]:
    """The rows in the listing shape: {path, status, module[, tag]}."""
    out = []
    for r in rows:
        entry = {"path": r.path, "status": r.status, "module": r.module}
        if r.tag:
            entry["tag"] = r.tag
        out.append(entry)
    return out


def glob_to_regex(pattern: str) -> "re.Pattern":
    """A path glob as a regex (not fnmatch / Path.full_match): `**` matches any depth INCLUDING zero directories (`src/**/*.ts` matches `src/a.ts`), `*` stays inside one
    path segment, `?` is one non-`/` character, `{a,b}` is an alternation. Anything else is literal."""
    pat = pattern.strip().replace("\\", "/")
    if pat.startswith("./"):
        pat = pat[2:]
    pat = pat.lstrip("/")
    out: list[str] = []
    i, n, depth = 0, len(pat), 0
    while i < n:
        c = pat[i]
        if c == "*":
            if pat[i:i + 2] == "**":
                if pat[i:i + 3] == "**/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "{":
            out.append("(?:")
            depth += 1
        elif c == "}" and depth:
            out.append(")")
            depth -= 1
        elif c == "," and depth:
            out.append("|")
        else:
            out.append(re.escape(c))
        i += 1
    out.append(")" * depth)
    return re.compile("".join(out) + r"\Z")


def _clip(line: str, cap: int = GREP_LINE_CAP) -> str:
    return line if len(line) <= cap else line[:cap] + "…"


def _int(value, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def grep_rows(rows, *, pattern: str, glob: str | None = None, type: str | None = None, mode: str = "content", ignore_case: bool = False,
              context: int = 0, offset: int = 0, limit: int = GREP_DEFAULT_ITEMS) -> dict:
    """Regex search over in-memory rows (completed files only, as the old tool_grep). Returns
    {results, truncated, next_offset, mode, status, reason?, scanned_files}. Never raises: a bad pattern / type / mode is status 'error'.
    Pagination units: HITS in content mode, FILES in files_with_matches and count modes. `next_offset` = offset + returned, present only when truncated.
    NOTE: the line cut before matching and the scan budget are mitigation, not a guarantee, against catastrophic regex backtracking (Python's `re` has no timeout)."""
    base = {"results": [], "truncated": False, "next_offset": None, "mode": mode, "scanned_files": 0}

    def fail(reason: str) -> dict:
        return {**base, "status": "error", "reason": reason}

    if mode not in ("content", "files_with_matches", "count"):
        return fail(f"unknown mode {mode!r} (content | files_with_matches | count)")
    if not isinstance(pattern, str) or not pattern:
        return fail("empty pattern")
    if len(pattern) > GREP_PATTERN_MAX:
        return fail(f"pattern longer than {GREP_PATTERN_MAX} characters")
    exts = None
    if type:
        exts = TYPE_EXTENSIONS.get(str(type).lower())
        if exts is None:
            return fail(f"unknown type {type!r} ({', '.join(sorted(TYPE_EXTENSIONS))})")
    try:
        rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        grx = glob_to_regex(glob) if glob else None
    except re.error as exc:
        return fail(f"invalid regex: {exc}")
    context = _int(context, 0, 0, 5)
    offset = _int(offset, 0, 0, 10 ** 9)
    limit = _int(limit, GREP_DEFAULT_ITEMS, 1, GREP_MAX_ITEMS)

    state = {"files": 0, "chars": 0, "stopped": False}

    def candidates():
        for r in rows:
            if r.status != "completed" or (grx and not grx.match(r.path)) or (exts and not r.path.lower().endswith(exts)):
                continue
            if state["files"] >= GREP_SCAN_FILES or state["chars"] >= GREP_SCAN_CHARS:
                state["stopped"] = True
                return
            state["files"] += 1
            state["chars"] += len(r.code)
            yield r

    def file_matches(r):
        lines = r.code.splitlines()
        for i, line in enumerate(lines):
            if rx.search(line[:GREP_LINE_SCAN_CAP]):
                yield i, lines

    results: list = []
    truncated, reason = False, None
    seen, used, done = 0, 0, False
    if mode == "content":
        for r in candidates():
            for i, lines in file_matches(r):
                if seen < offset:
                    seen += 1
                    continue
                hit = {"path": r.path, "line_no": i + 1, "line": _clip(lines[i].strip())}
                if context:
                    hit["before"] = [_clip(x) for x in lines[max(0, i - context):i]]
                    hit["after"] = [_clip(x) for x in lines[i + 1:i + 1 + context]]
                size = len(r.path) + len(hit["line"]) + sum(len(x) for x in hit.get("before", []) + hit.get("after", [])) + 16
                if len(results) >= limit or (results and used + size > GREP_TEXT_BUDGET):
                    truncated, reason, done = True, ("item_limit" if len(results) >= limit else "text_budget"), True
                    break
                results.append(hit)
                used += size
                seen += 1
            if done:
                break
    else:
        for r in candidates():
            matches = sum(1 for _ in file_matches(r)) if mode == "count" else (1 if next(file_matches(r), None) else 0)
            if not matches:
                continue
            if seen < offset:
                seen += 1
                continue
            if len(results) >= limit:
                truncated, reason = True, "item_limit"
                break
            results.append({"path": r.path} if mode == "files_with_matches" else {"path": r.path, "count": matches})
            seen += 1
    if state["stopped"] and not truncated:
        truncated, reason = True, "scan_budget"
    status = "empty" if not results and not truncated else ("truncated" if truncated else "ok")
    out = {**base, "results": results, "truncated": truncated, "next_offset": (offset + len(results)) if truncated else None, "status": status,
           "scanned_files": state["files"]}
    if reason:
        out["reason"] = reason
    return out


def grep_legacy(rows, pattern: str) -> list[dict]:
    """What tool_grep has always returned: completed files only, at most 50 hits {path, line_no, line (stripped)}; an invalid regex is [{"error": ...}]."""
    try:
        rx = re.compile(pattern)
    except re.error:
        return [{"error": f"Invalid regex: {pattern}"}]
    hits: list[dict] = []
    for r in rows:
        if r.status != "completed":
            continue
        for i, line in enumerate(r.code.splitlines(), 1):
            if rx.search(line):
                hits.append({"path": r.path, "line_no": i, "line": line.strip()})
                if len(hits) >= 50:
                    return hits
    return hits


def read_range(code: str, offset=None, limit=None) -> dict:
    """{content, total_lines, offset, limit, truncated, next_offset, status}. With neither offset nor limit this is the old read: the first 8,000 characters plus the old
    truncation marker. `offset` is a 0-based line; `limit` defaults to 400 lines and is at most 1,000."""
    lines = code.splitlines()
    total = len(lines)
    if offset is None and limit is None:
        n = len(code)
        content = code[:LEGACY_READ_CHARS] + (f"\n[... {n - LEGACY_READ_CHARS} chars truncated]" if n > LEGACY_READ_CHARS else "")
        return {"content": content, "total_lines": total, "offset": 0, "limit": total, "truncated": n > LEGACY_READ_CHARS, "next_offset": None,
                "status": "truncated" if n > LEGACY_READ_CHARS else "ok"}
    off = _int(offset, 0, 0, 10 ** 9)
    lim = _int(limit, READ_DEFAULT_LINES, 1, READ_MAX_LINES)
    if total and off >= total:
        return {"content": "", "total_lines": total, "offset": off, "limit": lim, "truncated": False, "next_offset": None, "status": "empty",
                "reason": f"offset {off} is past the end ({total} lines)"}
    chunk = lines[off:off + lim]
    more = off + lim < total
    return {"content": "\n".join(chunk), "total_lines": total, "offset": off, "limit": lim, "truncated": more, "next_offset": off + len(chunk) if more else None,
            "status": "truncated" if more else ("ok" if total else "empty")}
