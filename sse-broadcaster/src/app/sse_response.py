"""Glue for a FastAPI route: register a queue for a key and return the streaming response."""
from __future__ import annotations

from sse_starlette.sse import EventSourceResponse

from app.sse_broadcaster import _SSE_HEADERS, _event_stream, _register_queue


def stream_for(key: str, request) -> EventSourceResponse:
    """Authenticate and authorise BEFORE calling this (use a short-lived DB session for those checks, never one held for the whole stream)."""
    queue = _register_queue(key)
    return EventSourceResponse(_event_stream(key, queue, request), headers=_SSE_HEADERS)
