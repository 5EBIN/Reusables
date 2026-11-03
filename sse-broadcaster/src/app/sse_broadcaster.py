"""Server-Sent Events fan-out: one set of bounded queues per key (for example a resource id), a generator that streams them with a keepalive ping, and a broadcast that never blocks."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)

# key → list of queues for connected clients
_subscriptions: dict[str, list[asyncio.Queue]] = {}

# Confirmed common, well-documented failure class: any buffering reverse
# proxy in front of an SSE endpoint (nginx's default proxy_buffering on is
# the classic case; several managed-platform edge proxies do the same)
# turns a live event stream into delayed batches, or makes it look frozen
# until the proxy's buffer fills or the connection closes.
# X-Accel-Buffering: no is the standard application-side signal to disable
# that (works without needing proxy config access); Cache-Control: no-cache
# stops any HTTP cache from trying to buffer/replay the stream too.
_SSE_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}

# Bounded so a stalled/dead client (network drop without a clean TCP close,
# a sleeping laptop, a frozen tab) can't make its queue grow without limit
# while request.is_disconnected() hasn't caught up yet -- every other
# connected client's broadcasts don't get held up waiting for one slow
# consumer either, since put is never allowed to block (drop-oldest below).
# Generous relative to real event rates (worst case here is dozens of
# fast events, not hundreds) so this only ever engages for a
# genuinely stuck consumer, never a merely-busy one.
_SSE_QUEUE_MAXSIZE = 200
def _event_stream(key: str, queue: asyncio.Queue, request):
    async def generator() -> AsyncGenerator[dict, None]:
        try:
            yield {"event": "connected", "data": json.dumps({"key": key})}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {
                        "event": event.get("type", "message"),
                        "data": json.dumps({k: v for k, v in event.items() if k != "type"}),
                    }
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            if key in _subscriptions and queue in _subscriptions[key]:
                _subscriptions[key].remove(queue)
            if key in _subscriptions and not _subscriptions[key]:
                del _subscriptions[key]
    return generator()


def _register_queue(key: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=_SSE_QUEUE_MAXSIZE)
    _subscriptions.setdefault(key, []).append(queue)
    return queue
async def broadcast_event(key: str, event: dict[str, Any]) -> None:
    """Push an event to all connected SSE clients for a key.

    Never blocks: a queue at _SSE_QUEUE_MAXSIZE (a genuinely stuck consumer,
    not a merely busy one under normal event rates) drops its oldest queued
    event to make room for this one, rather than this call awaiting space
    forever and holding up every other connected client's broadcasts too.
    """
    for q in _subscriptions.get(key, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "[broadcast_event] queue for %s still full after dropping oldest — event dropped",
                    key,
                )


def get_emitter(key: str):
    """Return an async callable that broadcasts to all SSE clients for a project."""
    async def emit(event: dict[str, Any]) -> None:
        await broadcast_event(key, event)
    return emit
