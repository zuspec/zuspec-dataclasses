"""Runtime tests for Callable and Protocol port bindings.

Covers the four binding forms:
  1. Top-level Callable port bound via constructor kwarg
  2. Top-level Protocol port bound via constructor kwarg (duck-typed instance)
  3. Callable port bound via __bind__ in a containing component
  4. Protocol port bound via __bind__ (duck-typed instance or per-method)
"""
from __future__ import annotations
import asyncio
from typing import Callable, Awaitable, Protocol

import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# 1. Top-level Callable port bound via constructor kwarg
# ===========================================================================

def test_callable_port_bound_via_kwarg():
    """Top-level Callable port can be bound by passing an async callable as kwarg."""
    async def my_backend(x: zdc.u32) -> zdc.u32:
        return zdc.u32(int(x) * 2)

    @zdc.dataclass
    class Requester(zdc.Component):
        backend: Callable[[zdc.u32], Awaitable[zdc.u32]] = zdc.port()

    async def go():
        comp = Requester(backend=my_backend)
        assert comp.backend is my_backend
        r1 = await comp.backend(zdc.u32(5))
        assert int(r1) == 10
        r2 = await comp.backend(zdc.u32(21))
        assert int(r2) == 42

    _run(go())


# ===========================================================================
# 2. Top-level Protocol port bound via constructor kwarg (duck-typed)
# ===========================================================================

def test_protocol_port_bound_via_kwarg():
    """Top-level Protocol port can be bound by passing a duck-typed instance as kwarg."""
    calls = []

    class IStorage(Protocol):
        async def read(self, addr: zdc.u32) -> zdc.u32: ...
        async def write(self, addr: zdc.u32, data: zdc.u32) -> None: ...

    @zdc.dataclass
    class Bus(zdc.Component):
        mem: IStorage = zdc.port()

    class MockStorage:
        async def read(self, addr: zdc.u32) -> zdc.u32:
            calls.append(('read', int(addr)))
            return zdc.u32(0xDEAD)

        async def write(self, addr: zdc.u32, data: zdc.u32) -> None:
            calls.append(('write', int(addr), int(data)))

    async def go():
        storage = MockStorage()
        bus = Bus(mem=storage)
        val = await bus.mem.read(zdc.u32(0x100))
        assert int(val) == 0xDEAD
        await bus.mem.write(zdc.u32(0x200), zdc.u32(0xBEEF))

    _run(go())
    assert calls == [('read', 0x100), ('write', 0x200, 0xBEEF)]


# ===========================================================================
# 3. Callable port bound via __bind__ in containing component
# ===========================================================================

def test_callable_port_bound_via_bind():
    """Callable port on child component can be wired via parent __bind__."""
    calls = []

    @zdc.dataclass
    class Fetcher(zdc.Component):
        icache: Callable[[zdc.u32], Awaitable[zdc.u32]] = zdc.port()

    @zdc.dataclass
    class Memory(zdc.Component):
        async def fetch(self, addr: zdc.u32) -> zdc.u32:
            calls.append(int(addr))
            return zdc.u32(0x13)  # NOP

    @zdc.dataclass
    class Top(zdc.Component):
        fetcher: Fetcher = zdc.field()
        mem: Memory = zdc.field()

        def __bind__(self): return {
            self.fetcher.icache: self.mem.fetch,
        }

    async def go():
        top = Top()
        result = await top.fetcher.icache(zdc.u32(0x1000))
        assert int(result) == 0x13

    _run(go())
    assert calls == [0x1000]


# ===========================================================================
# 4a. Protocol port bound via __bind__ (duck-typed instance)
# ===========================================================================

def test_protocol_port_bound_via_bind_duck_typed():
    """Protocol port on child component can be wired via parent __bind__ using duck-typed impl."""
    calls = []

    class ICache(Protocol):
        async def load(self, addr: zdc.u32, funct3: zdc.u32) -> zdc.u32: ...
        async def store(self, addr: zdc.u32, data: zdc.u32, funct3: zdc.u32) -> None: ...

    @zdc.dataclass
    class LSU(zdc.Component):
        dcache: ICache = zdc.port()

    @zdc.dataclass
    class CacheSim(zdc.Component):
        _store: dict = zdc.field(default_factory=dict)

        async def load(self, addr: zdc.u32, funct3: zdc.u32) -> zdc.u32:
            calls.append(('load', int(addr)))
            return zdc.u32(self._store.get(int(addr), 0))

        async def store(self, addr: zdc.u32, data: zdc.u32, funct3: zdc.u32) -> None:
            calls.append(('store', int(addr), int(data)))
            self._store[int(addr)] = int(data)

    @zdc.dataclass
    class Top(zdc.Component):
        lsu: LSU = zdc.field()
        cache: CacheSim = zdc.field()

        def __bind__(self): return {
            self.lsu.dcache: self.cache,
        }

    async def go():
        top = Top()
        await top.lsu.dcache.store(zdc.u32(0x100), zdc.u32(42), zdc.u32(2))
        val = await top.lsu.dcache.load(zdc.u32(0x100), zdc.u32(2))
        assert int(val) == 42

    _run(go())
    assert ('store', 0x100, 42) in calls
    assert ('load', 0x100) in calls


# ===========================================================================
# 4b. Protocol port bound via __bind__ with per-method mapping
# ===========================================================================

def test_protocol_port_bound_via_bind_per_method():
    """Protocol port can be bound method-by-method via __bind__ (method-level key)."""
    load_calls = []
    store_calls = []

    class ICache(Protocol):
        async def load(self, addr: zdc.u32) -> zdc.u32: ...
        async def store(self, addr: zdc.u32, data: zdc.u32) -> None: ...

    @zdc.dataclass
    class LSU(zdc.Component):
        dcache: ICache = zdc.port()

    @zdc.dataclass
    class Top(zdc.Component):
        lsu: LSU = zdc.field()

        async def _do_load(self, addr: zdc.u32) -> zdc.u32:
            load_calls.append(int(addr))
            return zdc.u32(0xFF)

        async def _do_store(self, addr: zdc.u32, data: zdc.u32) -> None:
            store_calls.append((int(addr), int(data)))

        def __bind__(self): return {
            self.lsu.dcache.load:  self._do_load,
            self.lsu.dcache.store: self._do_store,
        }

    async def go():
        top = Top()
        val = await top.lsu.dcache.load(zdc.u32(0x200))
        assert int(val) == 0xFF
        await top.lsu.dcache.store(zdc.u32(0x200), zdc.u32(99))

    _run(go())
    assert load_calls == [0x200]
    assert store_calls == [(0x200, 99)]


# ===========================================================================
# 5. Validation: unbound callable port raises at top level
# ===========================================================================

def test_unbound_callable_port_raises():
    """Creating a top-level component with an unbound Callable port raises RuntimeError."""

    @zdc.dataclass
    class Requester(zdc.Component):
        backend: Callable[[zdc.u32], Awaitable[zdc.u32]] = zdc.port()

    with pytest.raises(RuntimeError, match="unbound ports"):
        Requester()  # no icache kwarg → should fail validation
