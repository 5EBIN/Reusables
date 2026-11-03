"""A value that must never be printed, logged or put in an error message.

`Secret` wraps an API key. `repr`, `str`, f-strings, `%` formatting and logging all show only the masked form (`sk-or-…abcd`); the real value is
available through `reveal()`, which only the code that builds the request header calls. JSON encoding and pickling are refused, so a secret cannot
leave through a serialised settings object either. `scrub()` removes a secret's real value from free text such as an exception message."""
from typing import Any


class Secret:
    __slots__ = ("_v",)

    def __init__(self, value: str | None):
        object.__setattr__(self, "_v", value or "")

    def reveal(self) -> str:
        return self._v

    def masked(self) -> str:
        v = self._v
        if len(v) < 12:
            return "…" if v else ""                       # too short to show any part safely
        return f"{'sk-or-' if v.startswith('sk-or-') else ''}…{v[-4:]}"

    def __bool__(self) -> bool:
        return bool(self._v)

    def __repr__(self) -> str:
        return f"Secret({self.masked()})"

    def __str__(self) -> str:
        return self.masked()

    def __format__(self, spec: str) -> str:
        return format(self.masked(), spec)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and other._v == self._v

    def __hash__(self) -> int:
        return hash(("Secret", len(self._v)))             # never derived from the value itself

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Secret is immutable")

    def __reduce__(self):
        raise TypeError("a Secret cannot be pickled")

    def __deepcopy__(self, memo):
        return self


def scrub(text: Any, *secrets: Secret | str | None) -> str:
    """Replace every real secret value in `text` with its masked form (for error messages and log lines)."""
    out = str(text)
    for s in secrets:
        if s is None:
            continue
        real = s.reveal() if isinstance(s, Secret) else str(s)
        if len(real) >= 8:
            out = out.replace(real, Secret(real).masked())
    return out
