"""Runtime implementations of pipeline hazard lock strategies.

These classes back the stub :mod:`~zuspec.dataclasses.pipeline_locks`
descriptors during ``rt`` execution.  They are instantiated lazily by
:meth:`~zuspec.dataclasses.rt.pipeline_rt.PipelineRuntime.get_lock_rt`.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Dict, List, Optional


class QueueLockRt:
    """FIFO-ordered stall lock rt implementation.

    Per-address FIFO of :class:`asyncio.Event` objects — one per outstanding
    writer.  Readers block until all preceding writers have called
    :meth:`release`.

    Per-task reservation tracking: each asyncio task that calls ``reserve()``
    gets its own ``Event`` stored in ``_task_events[(task, addr)]``.  When
    ``block()`` is called from the same task, it skips its own event and only
    waits for events added by *earlier* tasks (previous tokens in program order).
    """

    def __init__(self) -> None:
        self._queues: Dict[Any, List[asyncio.Event]] = defaultdict(list)
        # Maps (task, addr) -> the Event this task reserved for addr
        self._task_events: Dict[tuple, asyncio.Event] = {}

    async def reserve(self, addr, mode: str = "write") -> None:
        """Claim a write slot for *addr*.

        Args:
            addr: Resource address.
            mode: ``"write"`` (default) or ``"read"``.
        """
        if mode == "write":
            ev = asyncio.Event()
            self._queues[addr].append(ev)
            task = asyncio.current_task()
            self._task_events[(task, addr)] = ev

    async def block(self, addr) -> None:
        """Block until all preceding writers to *addr* have released.

        Only waits for events belonging to *other* tasks (earlier tokens).
        The calling task's own event (from a same-token ``reserve()``) is
        skipped — a token must not wait for itself to release.

        Returns:
            ``None`` (QueueLock has no bypass network).
        """
        task = asyncio.current_task()
        my_ev = self._task_events.get((task, addr))
        q = self._queues.get(addr, [])
        # Collect events from other tasks that are ahead of ours in the queue
        if my_ev is not None:
            try:
                my_idx = q.index(my_ev)
            except ValueError:
                my_idx = len(q)
            events_to_wait = q[:my_idx]
        else:
            events_to_wait = list(q)
        for ev in events_to_wait:
            if not ev.is_set():
                await ev.wait()
        return None

    def write(self, addr, value: Any) -> None:
        """No bypass; value is committed to backing store directly (no-op here)."""

    def release(self, addr) -> None:
        """Signal the head-of-queue event for *addr* and clean up task tracking.

        Args:
            addr: Resource address.
        """
        task = asyncio.current_task()
        self._task_events.pop((task, addr), None)
        q = self._queues.get(addr, [])
        if q:
            ev = q.pop(0)
            ev.set()


class BypassLockRt:
    """In-order lock with bypass network rt implementation.

    ``write()`` immediately resolves all pending :meth:`block` awaiters
    by fulfilling their futures with the written value.

    Args:
        bypass_latency: Cycles from ``write()`` to value availability
                        (currently unused in the rt — forwarded same-cycle).
    """

    def __init__(self, bypass_latency: int = 1) -> None:
        self._latency = bypass_latency
        self._writers: Dict[Any, int] = defaultdict(int)          # addr -> outstanding writer count
        self._bypass: Dict[Any, Any] = {}                          # addr -> forwarded value
        self._waiters: Dict[Any, List[asyncio.Future]] = defaultdict(list)

    async def reserve(self, addr, mode: str = "write") -> None:
        """Register an outstanding writer for *addr*.

        Args:
            addr: Resource address.
            mode: ``"write"`` (default) or ``"read"``.
        """
        if mode == "write":
            self._writers[addr] += 1

    async def block(self, addr) -> Optional[Any]:
        """Block until *addr* has been written (bypass available) or all writers drain.

        Args:
            addr: Resource address.

        Returns:
            The bypassed value if a writer called :meth:`write`; else ``None``.
        """
        if addr in self._bypass:
            return self._bypass[addr]
        if self._writers.get(addr, 0) > 0:
            loop = asyncio.get_event_loop()
            fut: asyncio.Future = loop.create_future()
            self._waiters[addr].append(fut)
            val = await fut
            return val
        return None

    def write(self, addr, value: Any) -> None:
        """Forward *value* to all pending :meth:`block` waiters for *addr*.

        Args:
            addr:  Resource address.
            value: Value to bypass-forward.
        """
        self._bypass[addr] = value
        for fut in self._waiters.pop(addr, []):
            if not fut.done():
                fut.set_result(value)

    def release(self, addr) -> None:
        """Decrement the outstanding-writer count for *addr*.

        Clears the bypass entry once all writers have released.

        Args:
            addr: Resource address.
        """
        if self._writers.get(addr, 0) > 0:
            self._writers[addr] -= 1
        if self._writers.get(addr, 0) == 0 and addr in self._bypass:
            del self._bypass[addr]
