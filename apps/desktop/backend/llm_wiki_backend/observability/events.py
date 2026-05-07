from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BackendEvent:
    event_type: str
    payload: dict[str, Any]


class EventHub:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[BackendEvent]] = set()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def subscribe(self) -> asyncio.Queue[BackendEvent]:
        queue: asyncio.Queue[BackendEvent] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[BackendEvent]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        loop = self._loop
        if loop is None:
            return

        event = BackendEvent(event_type=event_type, payload=payload)

        def _fanout() -> None:
            for queue in list(self._subscribers):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Drop on overload to keep the app responsive.
                    continue

        loop.call_soon_threadsafe(_fanout)


EVENT_HUB = EventHub()

