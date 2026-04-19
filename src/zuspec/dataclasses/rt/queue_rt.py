"""``QueueRT`` — asyncio.Queue-backed Queue for behavioral simulation."""
from __future__ import annotations

import asyncio
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class QueueRT(Generic[T]):
    """asyncio.Queue-backed Queue for behavioral (Level 0/1) simulation.

    This is the concrete object returned by ``zdc.queue(depth=N)`` during
    simulation.  The synthesis extractor never instantiates this directly.
    """

    def __init__(self, depth: int, element_type: Optional[type] = None):
        self._q: asyncio.Queue = asyncio.Queue(maxsize=depth)
        self._depth = depth
        self._element_type = element_type

    async def put(self, item: T) -> None:
        """Block until space is available, then enqueue ``item``."""
        await self._q.put(item)

    async def get(self) -> T:
        """Block until an item is available, then dequeue and return it."""
        return await self._q.get()

    def qsize(self) -> int:
        """Return the number of items currently in the queue."""
        return self._q.qsize()

    def full(self) -> bool:
        """True if the queue has reached its depth limit."""
        return self._q.full()

    def empty(self) -> bool:
        """True if the queue contains no items."""
        return self._q.empty()

    @property
    def depth(self) -> int:
        return self._depth

    def __repr__(self):
        return f"QueueRT(depth={self._depth}, qsize={self.qsize()})"
