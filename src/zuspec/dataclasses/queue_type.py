"""``zdc.Queue[T]`` and ``zdc.queue(depth=N)`` — bounded FIFO.

At simulation time a ``QueueRT`` backed by ``asyncio.Queue`` is returned.
At synthesis the IR extractor records the depth and element type and maps
the FIFO to a synchronous FIFO RTL structure.

Usage::

    @zdc.dataclass
    class MyComp(zdc.Component):
        _req_q: zdc.Queue[LoadReq] = zdc.queue(depth=4)

        @zdc.proc
        async def _producer(self):
            while True:
                req = LoadReq(addr=self.addr)
                await self._req_q.put(req)

        @zdc.proc
        async def _consumer(self):
            while True:
                req = await self._req_q.get()
                ...
"""
from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Queue(Generic[T]):
    """Bounded FIFO for inter-process communication inside a component.

    ``depth`` is mandatory and controls:
    - Python runtime: ``asyncio.Queue(maxsize=depth)``
    - C runtime: static ring buffer of ``depth`` elements
    - Synthesis: FIFO depth parameter
    """

    def __class_getitem__(cls, item):
        return _QueueAlias(cls, item)

    async def put(self, item: T) -> None:
        """Block until space is available, then enqueue ``item``."""
        raise NotImplementedError

    async def get(self) -> T:
        """Block until an item is available, then dequeue and return it."""
        raise NotImplementedError

    def qsize(self) -> int:
        """Return the number of items currently in the queue."""
        raise NotImplementedError

    def full(self) -> bool:
        """True if the queue has reached its depth limit."""
        raise NotImplementedError

    def empty(self) -> bool:
        """True if the queue contains no items."""
        raise NotImplementedError


class _QueueAlias:
    """``Queue[T]`` subscript result — used for type annotations."""

    def __init__(self, origin, item):
        self._origin = origin
        self._item = item

    def __repr__(self):
        return f"Queue[{self._item!r}]"


def queue(depth: int, *, element_type=None) -> "Queue":
    """Factory: declare a Queue field on a component.

    ``depth`` is mandatory.  At simulation time returns a ``QueueRT``
    instance backed by ``asyncio.Queue(maxsize=depth)``.

    Example::

        _req_q: zdc.Queue[LoadReq] = zdc.queue(depth=4)
    """
    if depth < 1:
        raise ValueError(f"queue(depth=...) requires depth >= 1, got {depth}")
    from zuspec.dataclasses.rt.queue_rt import QueueRT
    return QueueRT(depth=depth, element_type=element_type)
