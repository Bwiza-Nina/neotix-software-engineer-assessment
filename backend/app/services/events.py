import asyncio
from collections.abc import AsyncIterator

_subscribers: set[asyncio.Queue] = set()


def publish(event: dict) -> None:
    for queue in list(_subscribers):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def subscribe() -> AsyncIterator[dict]:
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    _subscribers.add(queue)
    try:
        while True:
            yield await queue.get()
    finally:
        _subscribers.discard(queue)
