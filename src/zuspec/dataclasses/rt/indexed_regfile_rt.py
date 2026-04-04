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
"""Runtime implementation of IndexedRegFile.

Design notes
------------
Two orthogonal concerns are kept separate:

* **Structural** — slot pools (asyncio.Semaphore) limit how many concurrent
  accesses of each type are in flight.  ``read_ports`` semaphore tokens for
  reads, ``write_ports`` tokens for writes.

* **Semantic** — register storage (a plain list) holds current values and is
  updated on write.  MLS does not model storage here; the RT is for
  simulation / functional coverage, not synthesis.

When ``shared_port=True`` a *single* semaphore of size 1 is shared by both
reads and writes, enforcing mutual exclusion — exactly modelling a true
single-port Block RAM.

x0 special case
---------------
* ``read(0)`` returns 0 immediately without acquiring a slot.
* ``write(0, val)`` is a no-op without acquiring a slot.
"""
from __future__ import annotations

import asyncio
import dataclasses as dc
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional


@dc.dataclass
class IndexedRegFileClaim:
    """Record of a completed register file access (useful for coverage)."""
    idx:  int
    data: int
    kind: str   # 'read' | 'write'


class _ReadContext:
    """Async context manager for a single register read."""

    __slots__ = ('_rt', '_idx', '_sem', '_val')

    def __init__(self, rt: 'IndexedRegFileRT', idx: int, sem: asyncio.Semaphore):
        self._rt  = rt
        self._idx = idx
        self._sem = sem
        self._val = 0

    async def __aenter__(self) -> int:
        # x0 is hardwired zero — no slot consumed
        if self._idx == 0:
            self._val = 0
            return 0
        await self._sem.acquire()
        self._val = self._rt._regs[self._idx]
        return self._val

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._idx != 0:
            self._sem.release()
        return False


class _WriteContext:
    """Async context manager for a single register write."""

    __slots__ = ('_rt', '_idx', '_val', '_sem')

    def __init__(self, rt: 'IndexedRegFileRT', idx: int, val: int,
                 sem: asyncio.Semaphore):
        self._rt  = rt
        self._idx = idx
        self._val = val
        self._sem = sem

    async def __aenter__(self) -> None:
        # x0 is hardwired zero — writes are silently discarded, no slot consumed
        if self._idx == 0:
            return
        await self._sem.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._idx != 0:
            if exc_type is None:
                self._rt._regs[self._idx] = self._val
            self._sem.release()
        return False


@dc.dataclass
class IndexedRegFileRT:
    """Runtime implementation of the IndexedRegFile protocol.

    Parameters
    ----------
    depth:
        Number of registers (e.g. 32 for RV32/RV64).
    read_ports:
        Maximum concurrent reads (structural port count).
    write_ports:
        Maximum concurrent writes (structural port count).
    shared_port:
        If ``True``, reads and writes share a single semaphore of size 1
        (true single-port mode).  If ``False``, reads and writes use
        independent semaphores and can overlap in the same cycle.
    """
    depth:       int  = 32
    read_ports:  int  = 2
    write_ports: int  = 1
    shared_port: bool = False

    # Internal storage and semaphores — initialised in __post_init__
    _regs:     List[int]              = dc.field(default_factory=list, init=False, repr=False)
    _read_sem: Optional[asyncio.Semaphore] = dc.field(default=None,   init=False, repr=False)
    _write_sem: Optional[asyncio.Semaphore] = dc.field(default=None,  init=False, repr=False)

    def __post_init__(self):
        self._regs = [0] * self.depth   # all registers initialise to 0

        if self.shared_port:
            # One shared semaphore: reads and writes compete for the single slot
            shared = asyncio.Semaphore(1)
            self._read_sem  = shared
            self._write_sem = shared
        else:
            # Independent semaphores: reads and writes can overlap
            self._read_sem  = asyncio.Semaphore(self.read_ports)
            self._write_sem = asyncio.Semaphore(self.write_ports)

    # ------------------------------------------------------------------
    # Public API  (matches IndexedRegFile protocol)
    # ------------------------------------------------------------------

    def read(self, idx: int) -> _ReadContext:
        """Return an async context manager that yields ``regs[idx]``.

        Reading register 0 (x0) always yields 0 without consuming a slot.

        Usage::

            async with regfile.read(rs1) as rs1_val:
                ...
        """
        return _ReadContext(self, idx, self._read_sem)

    async def read_all(self, *indices: int) -> tuple:
        """Read multiple registers concurrently, respecting port-count limits.

        Launches one coroutine per index via ``asyncio.gather``.  The
        underlying semaphore limits how many can proceed simultaneously, so
        if ``len(indices) > read_ports`` the excess reads are naturally
        queued and serialized in batches — the call always completes.

        Usage::

            rs1v, rs2v = await self.comp.regfile.read_all(d.rs1, d.rs2)

        Returns a tuple of values in the same order as *indices*.
        """
        async def _one(idx: int) -> int:
            async with self.read(idx) as val:
                return val

        return tuple(await asyncio.gather(*(_one(i) for i in indices)))

    def write(self, idx: int, val: int) -> _WriteContext:
        """Return an async context manager that writes ``val`` to ``regs[idx]``.

        Writing register 0 (x0) is a no-op; no slot is consumed.

        Usage::

            async with regfile.write(rd, result):
                pass
        """
        return _WriteContext(self, idx, val, self._write_sem)

    # ------------------------------------------------------------------
    # Direct register access (for reset / test setup)
    # ------------------------------------------------------------------

    def reset(self):
        """Reset all registers to 0."""
        for i in range(self.depth):
            self._regs[i] = 0

    def set_reg(self, idx: int, val: int):
        """Force-write a register value (bypasses port constraints, for setup)."""
        if 0 < idx < self.depth:
            self._regs[idx] = val

    def get_reg(self, idx: int) -> int:
        """Read a register value directly (bypasses port constraints, for checking)."""
        if idx == 0:
            return 0
        return self._regs[idx]
