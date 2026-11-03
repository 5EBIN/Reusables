"""Methods of FileToolTurn that were extracted verbatim: _call (dedupe, budget, error containment), _fit (cut a result to the budget and say so), _do_glob, _do_grep.
They are attached to the class at import time by app.file_tools_attach."""
from __future__ import annotations

import json
import logging
import re

from app.file_access import GLOB_DEFAULT_LIMIT, GLOB_MAX_LIMIT, ProjectScopeError, glob_to_regex, grep_rows, rows_listing

logger = logging.getLogger(__name__)


class _Methods:
    async def _call(self, tool: str, prefix: str, args: dict, handler) -> dict:
        key = tool + json.dumps(args, sort_keys=True, default=str)
        label = f"[{self.prefix}{self.round}] " + self._label(tool, args)
        if key in self.seen:
            rec = {"id": self._new_id(prefix), "tool": tool, "args": args, "round": self.round, "status": "already_loaded", "truncated": False, "next_offset": None,
                   "payload": None, "digest": None, "chars": 0, "label": label, "ref": self.seen[key]}
            self.records.append(rec)
            return rec
        left = self.budget_left()
        if left <= 0:
            self.stop_reason = self.stop_reason or "content_budget"
            rec = {"id": self._new_id(prefix), "tool": tool, "args": args, "round": self.round, "status": "truncated", "truncated": True, "next_offset": None,
                   "payload": {"reason": "content budget reached; nothing was loaded"}, "digest": {"reason": "content budget reached"}, "chars": 0, "label": label}
            self.records.append(rec)
            return rec
        try:
            self._check_scope(tool, args)
            out = await handler(args, left)
        except ProjectScopeError as exc:                         # an absolute or traversal-style path / glob: refused, never read
            out = {"status": "error", "reason": str(exc), "payload": {"error": str(exc)}, "digest": {"error": str(exc)}}
        except Exception as exc:
            logger.warning("[file_tools] %s failed: %s", tool, type(exc).__name__, exc_info=True)
            out = {"status": "error", "reason": f"{type(exc).__name__}", "payload": {"error": type(exc).__name__}, "digest": {"error": type(exc).__name__}}
        out = self._fit(out, left)
        chars = len(json.dumps(out.get("payload"), ensure_ascii=False, default=str)) if out.get("payload") is not None else 0
        self.round_chars += chars
        self.turn_chars += chars
        if self.turn_chars >= self.turn_budget:
            self.stop_reason = self.stop_reason or "content_budget"
        status = out.get("status", "ok")
        if status in ("error", "not_found", "empty", "unavailable") or out.get("truncated"):
            logger.info("[file_tools] %s -> %s%s", label, status, f" ({out['reason']})" if out.get("reason") else "")
        rec = {"id": self._new_id(prefix), "tool": tool, "args": args, "round": self.round, "status": status, "truncated": bool(out.get("truncated")),
               "next_offset": out.get("next_offset"), "reason": out.get("reason"), "payload": out.get("payload"), "digest": out.get("digest") or out.get("payload"),
               "chars": chars, "label": label}
        self.records.append(rec)
        if status not in ("error", "unavailable"):
            self.seen[key] = rec["id"]
        return rec

    def _fit(self, out: dict, left: int) -> dict:
        """Keep a result within the remaining budget: cut its content / list and say so (truncated + the next offset or range). Never hides that something was cut."""
        payload = out.get("payload")
        if not isinstance(payload, dict) or len(json.dumps(payload, ensure_ascii=False, default=str)) <= left:
            return out
        payload = dict(payload)
        if isinstance(payload.get("content"), str):
            keep_lines = payload["content"].split("\n")
            while keep_lines and len(json.dumps({**payload, "content": "\n".join(keep_lines)}, ensure_ascii=False)) > left:
                keep_lines = keep_lines[: max(0, int(len(keep_lines) * 0.8) - 1)]
            payload["content"] = "\n".join(keep_lines)
            payload["truncated"] = True
            payload["next_offset"] = (payload.get("offset") or 0) + len(keep_lines)
            out = {**out, "next_offset": payload["next_offset"]}
        else:
            for field_name in ("results", "filtered_files", "entries", "importers", "segments", "hits", "paths"):
                if isinstance(payload.get(field_name), list):
                    items = list(payload[field_name])
                    while items and len(json.dumps({**payload, field_name: items}, ensure_ascii=False, default=str)) > left:
                        items = items[: max(0, int(len(items) * 0.8) - 1)]
                    payload[field_name] = items
                    payload["truncated"] = True
                    payload["next_offset"] = (payload.get("offset") or 0) + len(items)
                    out = {**out, "next_offset": payload["next_offset"]}
                    break
        out = {**out, "payload": payload, "truncated": True, "reason": out.get("reason") or "content_budget"}
        if out.get("status") in ("ok", None):
            out["status"] = "truncated"
        self.stop_reason = self.stop_reason or ("content_budget" if self.turn_chars + left >= self.turn_budget else self.stop_reason)
        return out

    async def _do_glob(self, args: dict, left: int) -> dict:
        from app.file_access import GLOB_DEFAULT_LIMIT, GLOB_MAX_LIMIT, glob_to_regex, rows_listing
        pattern = args["pattern"]
        try:
            rx = glob_to_regex(pattern)
        except re.error as exc:
            return {"status": "error", "reason": f"invalid glob: {exc}", "payload": {"pattern": pattern, "filtered_files": []}}
        limit = max(1, min(GLOB_MAX_LIMIT, int(args.get("limit") or GLOB_DEFAULT_LIMIT)))
        listing = sorted((e for e in rows_listing(await self.rows()) if rx.match(e["path"])), key=lambda e: e["path"])
        shown = listing[:limit]
        for e in shown:
            if e not in self.filtered_files:
                self.filtered_files.append(e)
        payload = {"pattern": pattern, "filtered_files": shown, "total_matches": len(listing), "truncated": len(listing) > limit}
        status = "empty" if not listing else ("truncated" if payload["truncated"] else "ok")
        if status == "empty":
            payload["note"] = f"0 files match {pattern}"
        folders: dict = {}
        for e in shown:
            folders[e["path"].rsplit("/", 1)[0] if "/" in e["path"] else "."] = folders.get(e["path"].rsplit("/", 1)[0] if "/" in e["path"] else ".", 0) + 1
        digest = {"pattern": pattern, "count": len(listing), "truncated": payload["truncated"]}
        if len(shown) <= 50:
            digest["paths"] = [e["path"] for e in shown]
        else:
            digest["folders"] = dict(sorted(folders.items()))
        return {"status": status, "truncated": payload["truncated"], "payload": payload, "digest": digest}

    async def _do_grep(self, args: dict, left: int) -> dict:
        from app.file_access import grep_rows
        res = grep_rows(await self.rows(), pattern=args["pattern"], glob=args.get("glob"), type=args.get("type"), mode=args.get("mode", "content"),
                        ignore_case=bool(args.get("ignore_case")), context=args.get("context", 0), offset=args.get("offset", 0))
        payload = {"pattern": args["pattern"], **res, "offset": args.get("offset", 0)}
        per_file: dict = {}
        if res["mode"] == "content":
            for h in res["results"]:
                per_file.setdefault(h["path"], []).append(h)
            digest = {"pattern": args["pattern"], "mode": "content", "files": {p: {"hits": len(v), "lines": [f"{p}:{h['line_no']}:{h['line']}" for h in v[:3]]} for p, v in per_file.items()}}
        else:
            digest = {"pattern": args["pattern"], "mode": res["mode"], "results": res["results"][:20], "more": max(0, len(res["results"]) - 20)}
        digest.update({"truncated": res["truncated"], "next_offset": res["next_offset"]})
        return {"status": res["status"], "truncated": res["truncated"], "next_offset": res["next_offset"], "reason": res.get("reason"), "payload": payload, "digest": digest}
