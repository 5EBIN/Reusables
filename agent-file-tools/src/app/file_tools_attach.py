"""Attach the extracted methods to FileToolTurn (kept apart so each file stays close to its original)."""
from app.file_tools import FileToolTurn
from app.file_tools_slices import _Methods

for _name in ("_call", "_fit", "_do_glob", "_do_grep"):
    setattr(FileToolTurn, _name, getattr(_Methods, _name))
