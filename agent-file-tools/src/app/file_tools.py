"""One turn of file tools: run glob / grep / read requests under a character budget, remember what was already loaded, and say so when something was cut.

Further tools plug in through `extra_tools`: a mapping {tool name: async handler(args, left) -> result dict}. The handlers a host adds are its own business; this module only
budgets and records them. (The methods _call, _fit, _do_glob and _do_grep are the extracted ones, attached by app.file_tools_attach.)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Awaitable, Callable

from app.file_access import (GLOB_DEFAULT_LIMIT, GLOB_MAX_LIMIT, READ_DEFAULT_LINES, ProjectScopeError, _assert_in_project, glob_to_regex, grep_rows, read_range, rows_listing)
from app.file_tools_keys import exact_variant
from app.file_tools_models import GlobReq, GrepReq, ReadReq
from app.services.safe_paths import unsafe_path_reason

logger = logging.getLogger(__name__)

MAX_PER_ROUND = 5                  # requests per tool per round
ROUND_BUDGET = 20_000              # characters of NEW tool output one round may load
TURN_BUDGET = 60_000               # characters one turn may load in total
ITEM_MODELS = {"globs": GlobReq, "greps": GrepReq, "reads": ReadReq}
Handler = Callable[[dict, int], Awaitable[dict]]
RowsProvider = Callable[[], Awaitable[list]]


def effective_cap(raw, default: int, lo: int, hi: int) -> int:
    """A configured cap clamped to [lo, hi]; an unreadable value is replaced (WARNING), never trusted."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning("[file_tools] cap %r is not a number; using the default %d", raw, default)
        return default
    return max(lo, min(hi, value))


def normalize_flags(raw, known_keys: tuple[str, ...]) -> tuple[dict, list]:
    """(flags, ignored): a model's tool-choice JSON parsed into known keys. An unknown key that is an exact variant of one known key is used as that key; any other unknown key
    is recorded as "ignored: <key>"; an invalid item is dropped and recorded as "rejected: <key>[i]"; lists are cut to MAX_PER_ROUND."""
    from pydantic import ValidationError
    if not isinstance(raw, dict):
        return {}, ["rejected: flags are not a JSON object"]
    known, flags, ignored = set(known_keys), {}, []
    for key, value in raw.items():
        target = key if key in known else exact_variant(key, known)
        if target is None:
            ignored.append(f"ignored: {key}")
        elif target not in flags and value is not None:
            flags[target] = value
            if target != key:
                ignored.append(f"normalised: {key} -> {target}")
    for key, model in ITEM_MODELS.items():
        if key not in flags:
            continue
        items = flags[key] if isinstance(flags[key], list) else []
        clean = []
        for i, item in enumerate(items):
            if len(clean) >= MAX_PER_ROUND:
                ignored.append(f"rejected: {key}[{i}] (more than {MAX_PER_ROUND} per round)")
                continue
            try:
                parsed = model.model_validate({k: v for k, v in item.items() if v is not None} if isinstance(item, dict) else item)
            except ValidationError as exc:
                ignored.append(f"rejected: {key}[{i}] ({'; '.join(e['type'] for e in exc.errors()[:2])})")
                continue
            if key == "reads" and not parsed.path:
                ignored.append(f"rejected: reads[{i}] (needs path)")
                continue
            clean.append(parsed.model_dump(exclude_none=True))
        flags[key] = clean
    return flags, ignored


class FileToolTurn:
    """The tool session of ONE turn. Holds every result (id, args, status, payload, digest), and the budgets."""

    def __init__(self, rows_provider: RowsProvider, *, extra_tools: dict[str, Handler] | None = None, turn_budget: int = TURN_BUDGET, prefix: str = "r"):
        self.rows_provider, self.extra_tools = rows_provider, extra_tools or {}
        self.prefix, self.turn_budget = prefix, turn_budget
        self.records: list = []
        self.counters: dict = {}
        self.round = 0
        self.round_chars = 0
        self.turn_chars = 0
        self.seen: dict = {}
        self.stop_reason: str | None = None
        self.filtered_files: list = []
        self._rows = None

    async def rows(self):
        if self._rows is None:
            self._rows = await self.rows_provider()
        return self._rows

    def _new_id(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}{self.counters[prefix]}"

    def budget_left(self) -> int:
        return min(ROUND_BUDGET - self.round_chars, self.turn_budget - self.turn_chars)

    async def run_round(self, flags: dict, round_no: int) -> list:
        """Run the tool requests of `flags`. Returns the records this round produced."""
        self.round, self.round_chars, self._rows = round_no, 0, None
        plan = [("globs", "L", a, self._do_glob) for a in flags.get("globs", [])]
        plan += [("greps", "G", a, self._do_grep) for a in flags.get("greps", [])]
        plan += [("reads", "R", a, self._do_read) for a in flags.get("reads", [])]
        for name, handler in self.extra_tools.items():
            plan += [(name, name[:1].upper(), a, handler) for a in flags.get(name, [])]
        return [await self._call(tool, prefix, args, handler) for tool, prefix, args, handler in plan]

    @staticmethod
    def _label(tool: str, args: dict) -> str:
        if tool == "reads":
            return f"read:{args.get('path')}"
        if tool == "greps":
            return f"grep:{args.get('pattern')}" + (f" [{args['glob']}]" if args.get("glob") else "")
        if tool == "globs":
            return f"glob:{args.get('pattern')}"
        return tool

    @staticmethod
    def _check_scope(tool: str, args: dict) -> None:
        """Defence in depth: every path or glob a request names goes through the same guards."""
        value = args.get({"reads": "path", "globs": "pattern", "greps": "glob"}.get(tool, ""))
        if isinstance(value, str) and value:
            _assert_in_project(value)
        if tool == "reads":
            reason = unsafe_path_reason(args.get("path"))
            if reason:
                raise ProjectScopeError(f"unsafe path: {reason}")

    async def _do_read(self, args: dict, left: int) -> dict:
        row = next((r for r in await self.rows() if r.path == args.get("path")), None)
        if row is None:
            return {"status": "not_found", "reason": f"file not found: {args.get('path')}", "payload": {"path": args.get("path")}}
        got = read_range(row.code, args.get("offset"), args.get("limit") or READ_DEFAULT_LINES)
        payload = {"path": row.path, **{k: got[k] for k in ("content", "total_lines", "offset", "limit", "truncated", "next_offset")}}
        digest = {"path": row.path, "total_lines": got["total_lines"], "truncated": got["truncated"], "next_offset": got["next_offset"]}
        return {"status": got["status"], "truncated": got["truncated"], "next_offset": got["next_offset"], "reason": got.get("reason"), "payload": payload, "digest": digest}
