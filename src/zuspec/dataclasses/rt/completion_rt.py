"""``CompletionRT`` — asyncio.Future-backed Completion for behavioral simulation."""
from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

T = TypeVar("T")


class CompletionRT(Generic[T]):
    """asyncio.Future-backed Completion for behavioral (Level 0/1) simulation.

    This is the concrete object returned by ``zdc.Completion[T]()`` during
    simulation.  The synthesis extractor never instantiates this directly.
    """

    def __init__(self):
        self._future: asyncio.Future | None = None
        self._set = False

    def _get_future(self) -> asyncio.Future:
        if self._future is None:
            loop = asyncio.get_event_loop()
            self._future = loop.create_future()
        return self._future

    def set(self, value: T) -> None:
        """Set the result.  Non-blocking.  Raises if called more than once."""
        if self._set:
            raise RuntimeError("Completion.set() called more than once")
        self._set = True
        fut = self._get_future()
        if not fut.done():
            fut.set_result(value)

    def __await__(self):
        return self._get_future().__await__()

    @property
    def is_set(self) -> bool:
        """True after ``set()`` has been called."""
        return self._set

    def __repr__(self):
        state = "set" if self._set else "pending"
        return f"CompletionRT({state})"
