"""Unit tests for IndexedRegFile runtime and decorator."""
from __future__ import annotations
import asyncio
import dataclasses

import pytest

from zuspec.dataclasses.rt.indexed_regfile_rt import IndexedRegFileRT, IndexedRegFileClaim
from zuspec.dataclasses.decorators import indexed_regfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rf(depth=32, read_ports=2, write_ports=1, shared_port=False) -> IndexedRegFileRT:
    return IndexedRegFileRT(depth=depth, read_ports=read_ports,
                            write_ports=write_ports, shared_port=shared_port)


# ---------------------------------------------------------------------------
# TestIndexedRegFileClaim
# ---------------------------------------------------------------------------

def test_claim_stores_index_and_value():
    claim = IndexedRegFileClaim(idx=5, data=42, kind='read')
    assert claim.idx   == 5
    assert claim.data  == 42
    assert claim.kind  == 'read'


def test_claim_mutable_value():
    claim = IndexedRegFileClaim(idx=3, data=0, kind='write')
    claim.data = 99
    assert claim.data == 99


# ---------------------------------------------------------------------------
# TestSeparatePorts — read_ports=2, write_ports=1, shared_port=False
# ---------------------------------------------------------------------------

def test_separate_ports_read_returns_stored_value():
    """read() should return the value last written to the same index."""
    async def run():
        rf = _make_rf()
        rf._regs[7] = 0xDEAD
        async with rf.read(7) as val:
            assert val == 0xDEAD

    asyncio.run(run())


def test_separate_ports_write_updates_mem():
    """write() should update internal memory at the given index."""
    async def run():
        rf = _make_rf()
        async with rf.write(3, 0xBEEF):
            pass
        assert rf._regs[3] == 0xBEEF

    asyncio.run(run())


def test_read_concurrency_up_to_read_ports():
    """Two concurrent reads should both succeed with read_ports=2."""
    async def run():
        rf = _make_rf(read_ports=2)
        rf._regs[1] = 10
        rf._regs[2] = 20
        async with rf.read(1) as v1, rf.read(2) as v2:
            assert v1 == 10
            assert v2 == 20

    asyncio.run(run())


# ---------------------------------------------------------------------------
# TestWriteSerialization
# ---------------------------------------------------------------------------

def test_write_serialization():
    """Two writes must serialize (write_ports=1)."""
    async def run():
        rf = _make_rf(write_ports=1)
        results = []

        async def writer(idx, val):
            async with rf.write(idx, val):
                results.append((idx, val))

        await asyncio.gather(writer(5, 100), writer(6, 200))
        assert rf._regs[5] == 100
        assert rf._regs[6] == 200
        # Both writes completed exactly once
        assert len(results) == 2

    asyncio.run(run())


# ---------------------------------------------------------------------------
# TestX0Special — register zero is hardwired to zero
# ---------------------------------------------------------------------------

def test_read_x0_returns_zero_without_port():
    """read(0) must return 0 without consulting storage (x0 always zero)."""
    async def run():
        rf = _make_rf(read_ports=2)
        rf._regs[0] = 0xDEAD  # force non-zero to confirm bypass
        async with rf.read(0) as v:
            assert v == 0

    asyncio.run(run())


def test_write_x0_is_noop():
    """write(0, val) must not change mem[0] (RISC-V x0 is hardwired 0)."""
    async def run():
        rf = _make_rf()
        rf._regs[0] = 0
        async with rf.write(0, 0xCAFE):
            pass
        assert rf._regs[0] == 0

    asyncio.run(run())


# ---------------------------------------------------------------------------
# TestSharedPort — shared_port=True
# ---------------------------------------------------------------------------

def test_shared_port_read_and_write_serialize():
    """With shared_port=True a read and a write must serialize."""
    async def run():
        rf = _make_rf(read_ports=1, write_ports=1, shared_port=True)
        ops = []

        async def reader():
            async with rf.read(4) as v:
                ops.append('read')

        async def writer():
            async with rf.write(4, 42):
                ops.append('write')

        await asyncio.gather(reader(), writer())
        assert set(ops) == {'read', 'write'}

    asyncio.run(run())


def test_shared_port_uses_single_semaphore():
    """shared_port=True must store the same semaphore for reads and writes."""
    async def run():
        rf = _make_rf(read_ports=1, write_ports=1, shared_port=True)
        assert rf._read_sem is rf._write_sem

    asyncio.run(run())


# ---------------------------------------------------------------------------
# TestDecoratorMetadata
# ---------------------------------------------------------------------------

def test_indexed_regfile_decorator_metadata():
    """indexed_regfile() must embed correct metadata on the field."""
    f = indexed_regfile(read_ports=2, write_ports=1, shared_port=False)
    meta = f.metadata
    assert meta['kind']         == 'indexed_regfile'
    assert meta['read_ports']   == 2
    assert meta['write_ports']  == 1
    assert meta['shared_port']  is False


def test_indexed_regfile_decorator_defaults():
    """indexed_regfile() default values: 2R 1W separate ports (RISC-V standard)."""
    f = indexed_regfile()
    meta = f.metadata
    assert meta['read_ports']  == 2
    assert meta['write_ports'] == 1
    assert meta['shared_port'] is False


# ---------------------------------------------------------------------------
# TestReadAll
# ---------------------------------------------------------------------------

def test_read_all_two_values():
    """read_all returns a tuple of values in index order."""
    async def run():
        rf = _make_rf(read_ports=2)
        rf._regs[1] = 10
        rf._regs[2] = 20
        vals = await rf.read_all(1, 2)
        assert vals == (10, 20)

    asyncio.run(run())


def test_read_all_x0_is_zero():
    """read_all honours x0 == 0 convention."""
    async def run():
        rf = _make_rf(read_ports=2)
        rf._regs[0] = 0xDEAD   # force non-zero to confirm bypass
        rf._regs[5] = 42
        vals = await rf.read_all(0, 5)
        assert vals == (0, 42)

    asyncio.run(run())


def test_read_all_serializes_when_ports_exhausted():
    """read_all with more indices than ports serializes without deadlock."""
    async def run():
        rf = _make_rf(read_ports=1)
        for i in range(1, 5):
            rf._regs[i] = i * 10
        vals = await rf.read_all(1, 2, 3, 4)
        assert vals == (10, 20, 30, 40)

    asyncio.run(run())


def test_read_all_single_index():
    """read_all with one index works like a regular read."""
    async def run():
        rf = _make_rf(read_ports=2)
        rf._regs[7] = 99
        (val,) = await rf.read_all(7)
        assert val == 99

    asyncio.run(run())
