"""In-process pub/sub that feeds the SSE endpoint.

Keeps a short replay buffer per run so a browser that connects late still sees what
happened. Single-process only; swap for Postgres LISTEN/NOTIFY or Redis if you scale out.
"""

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator

HISTORY = 1000


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._history: dict[str, deque] = defaultdict(lambda: deque(maxlen=HISTORY))

    def publish(self, run_id: str, type_: str, **data: Any) -> None:
        event = {"type": type_, "ts": datetime.now(timezone.utc).isoformat(), **data}
        self._history[run_id].append(event)
        for q in list(self._subscribers[run_id]):
            q.put_nowait(event)

    async def subscribe(self, run_id: str) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue()
        for event in list(self._history[run_id]):
            q.put_nowait(event)
        self._subscribers[run_id].add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers[run_id].discard(q)
