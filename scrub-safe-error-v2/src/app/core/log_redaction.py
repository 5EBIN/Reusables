"""
A credential in a URL query string must never reach a log line.

Browser EventSource cannot set an Authorization header, so a session token may travel as `?token=<jwt>`. The server access log prints the full request path, so every such connection would write a live token into the logs. The filter below replaces the value of any `token`-like query parameter with [REDACTED] in everything the access / error loggers and the root handlers format.
"""
from __future__ import annotations

import logging
import re

# `token=`, `access_token=`, `id_token=`, `refresh_token=` (and the common `apikey` / `api_key`) as a query parameter anywhere in the text.
_SECRET_PARAM = re.compile(r"(?i)((?:[?&]|\b)(?:token|access_token|id_token|refresh_token|api_key|apikey)=)[^&\s\"'<>]+")
REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    return _SECRET_PARAM.sub(lambda m: m.group(1) + REDACTED, text)


class RedactSecretsFilter(logging.Filter):
    """Rewrites the record in place: the message template and every string argument. Never drops a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.args:
                # KEEP the shape of `args`: uvicorn's AccessFormatter unpacks exactly five values from record.args on every access-log line, so clearing it breaks that log.
                # Redact each string argument in place (the access log carries the path, with ?token=, as an argument) and leave the template alone: redacting a template such as
                # "?token=%s" would replace its placeholder and make the formatting fail.
                if isinstance(record.args, tuple):
                    record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
                elif isinstance(record.args, dict):
                    record.args = {k: (redact(v) if isinstance(v, str) else v) for k, v in record.args.items()}
                # Last resort for a secret that only appears once the message is formatted (a bare token passed to "?token=%s", or an object that prints one): then the message
                # is replaced by its redacted form and args dropped. Access-log records never get here, because their string arguments were redacted above.
                formatted = record.getMessage()
                clean = redact(formatted)
                if clean != formatted:
                    record.msg, record.args = clean, None
            elif isinstance(record.msg, str):
                record.msg = redact(record.msg)
        except Exception:                                   # a logging filter must never break logging
            pass
        return True


_FILTER = RedactSecretsFilter()
_LOGGERS = ("uvicorn", "uvicorn.access", "uvicorn.error", "httpx", "httpcore")


def install_log_redaction() -> None:
    """Idempotent. Attach the filter to uvicorn's loggers AND their handlers (uvicorn configures its own handlers) and to the root handlers."""
    targets: list = [logging.getLogger(name) for name in _LOGGERS] + [logging.getLogger()]
    for target in list(targets):
        if _FILTER not in target.filters:
            target.addFilter(_FILTER)
        for handler in list(target.handlers):
            if _FILTER not in handler.filters:
                handler.addFilter(_FILTER)
