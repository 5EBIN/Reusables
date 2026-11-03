"""
How a "non-fatal" step reports its failure. Before, `except Exception: logger.warning("... (non-fatal)")` hid programming errors (a NameError, a TypeError, a wrong attribute)
behind the same quiet line as a database blip; runs crashed on TypeErrors that were first swallowed this way.

  soft_failure(label, exc, detail=None)   call it in an `except Exception as exc:` block. EXPECTED errors (database, timeout, HTTP, OS) log a warning, as before. A PROGRAMMING error
                                          (NameError, UnboundLocalError, TypeError, AttributeError, KeyError, ImportError) is logged at ERROR with its traceback, counted, and
                                          re-raised unless the environment is production (tests and local runs fail loudly; production keeps going). Anything else logs a warning.
  soft_step(label)                        the same as a `with` block, for new code.
  counts()                                {label: n} programming errors seen in this process.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import Counter

logger = logging.getLogger(__name__)

PROGRAMMING_ERRORS = (NameError, UnboundLocalError, TypeError, AttributeError, KeyError, ImportError)


def _expected_errors() -> tuple:
    out: list = [asyncio.TimeoutError, TimeoutError, OSError]
    try:
        from sqlalchemy.exc import SQLAlchemyError
        out.append(SQLAlchemyError)
    except Exception:
        pass
    try:
        import httpx
        out.append(httpx.HTTPError)
    except Exception:
        pass
    return tuple(out)


_counts: Counter = Counter()


def counts() -> dict:
    return dict(_counts)


def _is_production() -> bool:
    try:
        from app._stubs import get_settings
        return get_settings().treated_as_production              # only an explicit local value (development, dev, local, test) fails loudly; unset / staging / production go on
    except Exception:
        return True                                    # when in doubt, behave like production: log and keep going


def _head(label: str) -> str:
    """"stage context lookup" -> "[stage] context lookup failed": the log line keeps the shape the old plain warnings had."""
    tag, _, rest = label.partition(" ")
    return f"[{tag}] {rest + ' ' if rest else ''}failed"


def soft_failure(label: str, exc: BaseException, detail=None, *, expected: tuple | None = None, message: bool = True) -> None:
    """See the module docstring. Re-raises `exc` for a programming error outside production; otherwise returns."""
    where = f" ({detail})" if detail is not None else ""
    shown = str(exc) if message else type(exc).__name__          # message=False: the class only, for a site that never logged the text
    if isinstance(exc, expected if expected is not None else _expected_errors()):
        logger.warning("%s (non-fatal)%s: %s", _head(label), where, shown)
        return
    if isinstance(exc, PROGRAMMING_ERRORS):
        _counts[label] += 1
        logger.error("%s (non-fatal) with a programming error, %s%s: %s", _head(label), type(exc).__name__, where, shown, exc_info=exc)
        if not _is_production():
            raise exc
        return
    logger.warning("%s (non-fatal)%s: %s", _head(label), where, shown)


@contextlib.contextmanager
def soft_step(label: str, detail=None, *, expected: tuple | None = None):
    try:
        yield
    except Exception as exc:
        soft_failure(label, exc, detail, expected=expected)
