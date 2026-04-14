"""Unit tests for IndexedPool runtime and decorator."""
from __future__ import annotations
import asyncio
import pytest

from zuspec.dataclasses.rt.indexed_pool_rt import IndexedPoolRT
from zuspec.dataclasses.decorators import indexed_pool


def _make(depth=8, noop_idx=None) -> IndexedPoolRT:
    return IndexedPoolRT(depth=depth, noop_idx=noop_idx)


# ---------------------------------------------------------------------------
# Basic lock / share semantics
# ---------------------------------------------------------------------------

def test_lock_exclusive():
    """A second lock on the same index must wait for the first to release."""
    async def run():
        pool = _make()
        order = []

        async def first():
            async with pool.lock(3):
                order.append('A-in')
                await asyncio.sleep(0)   # yield so second() can attempt
                order.append('A-out')

        async def second():
            await asyncio.sleep(0)       # let first() acquire first
            async with pool.lock(3):
                order.append('B-in')

        await asyncio.gather(first(), second())
        assert order == ['A-in', 'A-out', 'B-in']

    asyncio.run(run())


def test_share_concurrent():
    """Multiple shares on the same index succeed concurrently."""
    async def run():
        pool = _make()
        entered = []

        async def reader(name):
            async with pool.share(2):
                entered.append(name)
                await asyncio.sleep(0)

        await asyncio.gather(reader('A'), reader('B'), reader('C'))
        assert set(entered) == {'A', 'B', 'C'}

    asyncio.run(run())


def test_lock_blocks_share():
    """share() on an index blocks while lock() is held on that index."""
    async def run():
        pool = _make()
        order = []

        async def writer():
            async with pool.lock(5):
                order.append('lock-in')
                await asyncio.sleep(0)
                order.append('lock-out')

        async def reader():
            await asyncio.sleep(0)      # let writer acquire first
            async with pool.share(5):
                order.append('share-in')

        await asyncio.gather(writer(), reader())
        assert order == ['lock-in', 'lock-out', 'share-in']

    asyncio.run(run())


def test_share_blocks_lock():
    """lock() on an index blocks while share() is held on that index."""
    async def run():
        pool = _make()
        order = []

        async def reader():
            async with pool.share(7):
                order.append('share-in')
                await asyncio.sleep(0)
                order.append('share-out')

        async def writer():
            await asyncio.sleep(0)
            async with pool.lock(7):
                order.append('lock-in')

        await asyncio.gather(reader(), writer())
        assert order == ['share-in', 'share-out', 'lock-in']

    asyncio.run(run())


def test_independent_indices_do_not_block():
    """lock() on index A does not block share() on index B."""
    async def run():
        pool = _make()
        order = []

        async def writer():
            async with pool.lock(1):
                order.append('lock-1')
                await asyncio.sleep(0)

        async def reader():
            async with pool.share(2):
                order.append('share-2')

        await asyncio.gather(writer(), reader())
        assert 'lock-1' in order and 'share-2' in order

    asyncio.run(run())


# ---------------------------------------------------------------------------
# noop_idx semantics
# ---------------------------------------------------------------------------

def test_noop_lock_does_not_block():
    """lock(noop_idx) completes immediately without blocking."""
    async def run():
        pool = _make(noop_idx=0)
        entered = False
        async with pool.lock(0):
            entered = True
        assert entered

    asyncio.run(run())


def test_noop_share_does_not_block():
    """share(noop_idx) completes immediately without blocking."""
    async def run():
        pool = _make(noop_idx=0)
        entered = False
        async with pool.share(0):
            entered = True
        assert entered

    asyncio.run(run())


def test_noop_lock_and_regular_share_coexist():
    """lock(noop_idx) and share(regular) don't interfere with each other."""
    async def run():
        pool = _make(noop_idx=0)
        results = []

        async def a():
            async with pool.lock(0):
                results.append('noop-lock')

        async def b():
            async with pool.share(5):
                results.append('share-5')

        await asyncio.gather(a(), b())
        assert set(results) == {'noop-lock', 'share-5'}

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Inspection helpers
# ---------------------------------------------------------------------------

def test_is_locked():
    async def run():
        pool = _make()
        assert not pool.is_locked(3)
        ctx = pool.lock(3)
        await ctx.__aenter__()
        assert pool.is_locked(3)
        await ctx.__aexit__(None, None, None)
        assert not pool.is_locked(3)

    asyncio.run(run())


def test_reader_count():
    async def run():
        pool = _make()
        assert pool.reader_count(4) == 0
        ctx = pool.share(4)
        await ctx.__aenter__()
        assert pool.reader_count(4) == 1
        await ctx.__aexit__(None, None, None)
        assert pool.reader_count(4) == 0

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Decorator metadata
# ---------------------------------------------------------------------------

def test_decorator_metadata():
    f = indexed_pool(depth=32, noop_idx=0)
    meta = f.metadata
    assert meta['kind']     == 'indexed_pool'
    assert meta['depth']    == 32
    assert meta['noop_idx'] == 0


def test_decorator_defaults():
    f = indexed_pool()
    meta = f.metadata
    assert meta['depth']    == 32
    assert meta['noop_idx'] is None
