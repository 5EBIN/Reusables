import asyncio

from app import sse_broadcaster as S


def test_broadcast_reaches_every_queue_and_drops_oldest_when_full():
    S._subscriptions.clear()
    a, b = S._register_queue('k'), S._register_queue('k')
    asyncio.run(S.broadcast_event('k', {'type': 'x', 'n': 1}))
    assert a.qsize() == 1 and b.qsize() == 1
    for i in range(S._SSE_QUEUE_MAXSIZE + 5):
        asyncio.run(S.broadcast_event('k', {'type': 'x', 'n': i}))
    assert a.qsize() == S._SSE_QUEUE_MAXSIZE
    assert a.get_nowait()['n'] >= 5
