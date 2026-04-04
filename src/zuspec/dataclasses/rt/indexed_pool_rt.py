#****************************************************************************
# Copyright 2019-2026 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
"""Runtime implementation of IndexedPool.

Design notes
------------
Each slot in the pool is an independent readers-writer lock implemented with
``asyncio.Condition``.  The condition variable carries two counters:

* ``_readers`` — number of active ``share()`` claims
* ``_writers`` — 1 while a ``lock()`` claim is held, 0 otherwise

Invariant maintained by the condition:
* A new reader may proceed only when ``_writers == 0``.
* A new writer may proceed only when ``_writers == 0 and _readers == 0``.

noop_idx
--------
When ``noop_idx`` is set, ``lock(noop_idx)`` and ``share(noop_idx)`` return
context managers that are immediate no-ops — no semaphore or condition is
touched.  This models RISC-V ``x0`` (hardwired zero): writing x0 is
discarded, reading x0 always yields 0, and neither operation should consume
a scoreboard slot or generate hazard comparators.
"""
from __future__ import annotations

import asyncio
import dataclasses as dc
from typing import List, Optional


# ---------------------------------------------------------------------------
# Per-slot readers-writer lock
# ---------------------------------------------------------------------------

class _IndexedSlot:
    """Asyncio-based readers-writer lock for a single pool slot."""

    __slots__ = ('_readers', '_writers', '_cond')

    def __init__(self):
        self._readers: int = 0
        self._writers: int = 0
        self._cond = asyncio.Condition()

    async def acquire_read(self):
        async with self._cond:
            while self._writers > 0:
                await self._cond.wait()
            self._readers += 1

    async def release_read(self):
        async with self._cond:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    async def acquire_write(self):
        async with self._cond:
            while self._writers > 0 or self._readers > 0:
                await self._cond.wait()
            self._writers = 1

    async def release_write(self):
        async with self._cond:
            self._writers = 0
            self._cond.notify_all()


# ---------------------------------------------------------------------------
# Context managers
# ---------------------------------------------------------------------------

class _LockContext:
    """Async context manager for an exclusive (write) claim on one slot."""

    __slots__ = ('_slot', '_active')

    def __init__(self, slot: Optional[_IndexedSlot]):
        self._slot   = slot   # None → noop_idx path
        self._active = False

    async def __aenter__(self):
        if self._slot is not None:
            await self._slot.acquire_write()
            self._active = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._active:
            await self._slot.release_write()
        return False


class _ShareContext:
    """Async context manager for a shared (read) claim on one slot."""

    __slots__ = ('_slot', '_active')

    def __init__(self, slot: Optional[_IndexedSlot]):
        self._slot   = slot   # None → noop_idx path
        self._active = False

    async def __aenter__(self):
        if self._slot is not None:
            await self._slot.acquire_read()
            self._active = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._active:
            await self._slot.release_read()
        return False


# ---------------------------------------------------------------------------
# IndexedPoolRT
# ---------------------------------------------------------------------------

@dc.dataclass
class IndexedPoolRT:
    """Runtime implementation of the IndexedPool protocol.

    Parameters
    ----------
    depth:
        Number of addressable slots (e.g. 32 for a RISC-V register file).
    noop_idx:
        Optional index whose lock/share operations are structural no-ops.
        Use ``noop_idx=0`` for RISC-V (x0 is hardwired zero).
    """
    depth:    int           = 32
    noop_idx: Optional[int] = None

    _slots: List[_IndexedSlot] = dc.field(
        default_factory=list, init=False, repr=False)

    def __post_init__(self):
        self._slots = [_IndexedSlot() for _ in range(self.depth)]

    # ------------------------------------------------------------------
    # Public API  (matches IndexedPool protocol)
    # ------------------------------------------------------------------

    def lock(self, idx: int) -> _LockContext:
        """Return an async context manager for an exclusive claim on slot *idx*.

        Usage::

            async with pool.lock(d.rd):
                ...  # rd reserved for writes; concurrent share(rd) blocks
        """
        slot = None if idx == self.noop_idx else self._slots[idx]
        return _LockContext(slot)

    def share(self, idx: int) -> _ShareContext:
        """Return an async context manager for a shared claim on slot *idx*.

        Usage::

            async with pool.share(d.rs1):
                ...  # proceeds when no lock(rs1) is active
        """
        slot = None if idx == self.noop_idx else self._slots[idx]
        return _ShareContext(slot)

    # ------------------------------------------------------------------
    # Inspection helpers (for tests / coverage)
    # ------------------------------------------------------------------

    def is_locked(self, idx: int) -> bool:
        """Return True if slot *idx* is currently exclusively locked."""
        if idx == self.noop_idx or idx >= self.depth:
            return False
        return self._slots[idx]._writers > 0

    def reader_count(self, idx: int) -> int:
        """Return the number of active share claims on slot *idx*."""
        if idx == self.noop_idx or idx >= self.depth:
            return 0
        return self._slots[idx]._readers
