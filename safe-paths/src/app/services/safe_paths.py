"""
app/services/safe_paths.py

Generated file paths come from model output (steerable by input text, uploads, pasted logs), so they are
untrusted wherever they become a place on disk or a database row.

  * unsafe_path_reason(rel)   -> None when `rel` is a safe PROJECT-RELATIVE posix path, else the reason it is not.
  * safe_join(root, rel)      -> the destination Path, or raises UnsafePathError (also when the resolved path, following
                                 symlinked parents, leaves `root`).
  * safe_write(root, rel, text) -> writes the file; an unsafe path is logged and skipped (returns False), never written.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_DRIVE = re.compile(r"^[A-Za-z]:")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
MAX_PATH_LEN = 512


class UnsafePathError(ValueError):
    pass


def unsafe_path_reason(rel) -> str | None:
    if not isinstance(rel, str) or not rel:
        return "empty or non-string path"
    if len(rel) > MAX_PATH_LEN:
        return "path too long"
    if _CONTROL.search(rel):
        return "control character or NUL byte"
    if "\\" in rel:
        return "backslash"
    if rel.startswith("/"):
        return "absolute path"
    if _DRIVE.match(rel) or ":" in rel.split("/", 1)[0]:
        return "drive letter or scheme"
    parts = rel.split("/")
    if "" in parts:
        return "empty segment"
    if ".." in parts:
        return "parent-directory segment"
    return None


def safe_join(root, rel) -> Path:
    reason = unsafe_path_reason(rel)
    if reason:
        raise UnsafePathError(f"unsafe file path {rel!r}: {reason}")
    base = Path(root).resolve()
    dest = (base / rel).resolve(strict=False)           # follows symlinked parents that already exist
    if dest != base and base not in dest.parents:
        raise UnsafePathError(f"unsafe file path {rel!r}: resolves outside the project root")
    return base / rel


def safe_write(root, rel, text: str, *, encoding: str = "utf-8") -> bool:
    try:
        dest = safe_join(root, rel)
    except UnsafePathError as exc:
        logger.warning("[safe_paths] file NOT written: %s", exc)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding=encoding)
    return True
