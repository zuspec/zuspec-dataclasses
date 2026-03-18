"""Flow-object runtime helpers for PSS Buffer, Stream, and State semantics."""
from __future__ import annotations

import asyncio
import dataclasses as dc
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dc.dataclass
class BufferInstance(Generic[T]):
    """Wraps a Buffer object.

    PSS semantics: one producer writes the buffer; N consumers may read it
    sequentially after the producer completes.  The producer calls
    ``set_ready()`` after its ``body()``; consumers call ``await wait_ready()``
    which blocks until the producer has finished.
    """

    obj: T
    _ready: asyncio.Future = dc.field(init=False)

    def __post_init__(self) -> None:
        loop = asyncio.get_event_loop()
        self._ready = loop.create_future()

    def set_ready(self) -> None:
        """Mark the buffer as produced (call from the producing action's body)."""
        if not self._ready.done():
            self._ready.set_result(self.obj)

    async def wait_ready(self) -> T:
        """Block until the producer has called ``set_ready()``."""
        return await self._ready


@dc.dataclass
class StreamInstance(Generic[T]):
    """Connects one producer and one consumer via an asyncio queue.

    PSS semantics: producer and consumer execute in parallel; the channel
    has capacity 1, so the producer blocks until the consumer has received
    the previous item (back-pressure).
    """

    _queue: asyncio.Queue = dc.field(
        default_factory=lambda: asyncio.Queue(maxsize=1)
    )

    async def put(self, obj: T) -> None:
        """Send an object (blocks if the consumer has not yet called get)."""
        await self._queue.put(obj)

    async def get(self) -> T:
        """Receive an object (blocks until the producer sends one)."""
        return await self._queue.get()


@dc.dataclass
class StatePool(Generic[T]):
    """Manages a single mutable state object.

    PSS semantics:
    - One writer at a time (exclusive); waits for all readers to finish first.
    - Multiple concurrent readers allowed; writer is excluded.
    - ``initial`` is ``True`` until the first write completes.
    """

    current: Optional[T] = None
    initial: bool = True
    _writer_lock: asyncio.Lock = dc.field(default_factory=asyncio.Lock)
    _reader_count: int = dc.field(default=0, repr=False)
    _no_readers: asyncio.Event = dc.field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        self._no_readers.set()  # no active readers initially

    # ------------------------------------------------------------------
    # Writer API
    # ------------------------------------------------------------------

    async def write_acquire(self) -> None:
        """Acquire exclusive write access; blocks until all readers finish."""
        await self._writer_lock.acquire()
        # Spin-wait for readers to drain (they don't hold the lock)
        while self._reader_count > 0:
            self._no_readers.clear()
            await self._no_readers.wait()

    def write_release(self, new_state: T) -> None:
        """Commit the new state and release write access."""
        self.current = new_state
        self.initial = False
        self._writer_lock.release()

    # ------------------------------------------------------------------
    # Reader API
    # ------------------------------------------------------------------

    async def read_acquire(self) -> T:
        """Start a read; returns current state (does not block writers directly)."""
        self._reader_count += 1
        return self.current

    def read_release(self) -> None:
        """Finish a read; signal the writer if no more readers remain."""
        self._reader_count -= 1
        if self._reader_count == 0:
            self._no_readers.set()
