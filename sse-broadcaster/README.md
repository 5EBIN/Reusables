# sse-broadcaster

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
Per-key queues for server-sent events: bounded queues, drop-oldest on a stuck consumer, 15 s keepalive ping, cleanup on disconnect, a never-blocking `broadcast_event`, and a FastAPI helper that returns the stream.

## Problem it solved
One stuck browser tab must not hold up every other client or exhaust the database pool.

## Public interface
* `app/sse_broadcaster.py`: `async def broadcast_event(key: str, event: dict[str, Any]) -> None`
* `app/sse_broadcaster.py`: `def get_emitter(key: str)`
* `app/sse_response.py`: `def stream_for(key: str, request) -> EventSourceResponse`

## Dependencies
Python (`deps.txt`): `sse-starlette>=2.1`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Single process: with several replicas an event does not reach clients on another one. Authenticate with a short-lived DB session, never one held for the stream.

## Quality
B (1 test copied)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
Register a queue per connection, broadcast with `broadcast_event(key, {...})`.
