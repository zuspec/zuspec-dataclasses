from __future__ import annotations
import asyncio
import dataclasses as dc
from typing import Any, Callable, List, Optional, Awaitable
from ..types import BufferPool

@dc.dataclass
class ListBufferPool[T](BufferPool[T]):
    items: List[T] = dc.field()
    select: Callable[[List[T]],Awaitable[T]] = dc.field(init=False)
    _sel_idx: int = dc.field(default=0)
    _ev: asyncio.Event = dc.field(default_factory=asyncio.Event)
    _waiters: int = dc.field(default=0)

    def __post_init__(self):
        self.select = self._select

    def put(self, item: T):
        """Add an item to the pool and notify any blocked get() callers."""
        self.items.append(item)
        self._ev.set()

    async def get(self, 
                  where : Optional[Callable[[T],bool]] = None,
                  select : Optional[Callable[[List[T]],Awaitable[T]]] = None) -> T:
        select = self.select if select is None else select
        while True:
            items = self.items if where is None else list(filter(where, self.items))
            if items:
                return await select(items)
            # No matching items yet — wait for a put()
            self._waiters += 1
            await self._ev.wait()
            self._waiters -= 1
            if self._waiters == 0:
                self._ev.clear()

    async def _select(self, items : List[T]) -> T:
        """pseudo-walking selection of items"""
        idx = self._sel_idx % len(items)
        self._sel_idx = idx + 1
        return items[idx]
