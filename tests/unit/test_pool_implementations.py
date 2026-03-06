"""Unit tests for ListClaimPool and ListBufferPool."""
from __future__ import annotations
import asyncio

from zuspec.dataclasses.types import ClaimPool, BufferPool, u32, u8


# ---------------------------------------------------------------------------
# ListClaimPool tests (via ClaimPool.fromList)
# ---------------------------------------------------------------------------

def test_claim_pool_lock_basic():
    """Lock a single resource and verify the claim holds the right value."""
    async def run():
        pool: ClaimPool[str] = ClaimPool[str].fromList(["a", "b", "c"])
        claim = await pool.lock()
        assert claim.t in ("a", "b", "c")
        pool.drop(claim)

    asyncio.run(run())


def test_claim_pool_lock_exclusive():
    """A locked resource cannot be locked again until dropped."""
    async def run():
        pool: ClaimPool[str] = ClaimPool[str].fromList(["only"])

        claim1 = await pool.lock()
        assert claim1.t == "only"

        # Second lock should block; race it with a drop
        locked_second = []

        async def try_lock():
            c = await pool.lock()
            locked_second.append(c)

        task = asyncio.create_task(try_lock())
        # Yield so the task starts and blocks
        await asyncio.sleep(0)
        assert locked_second == [], "Second lock should still be waiting"

        pool.drop(claim1)
        await task

        assert len(locked_second) == 1
        assert locked_second[0].t == "only"
        pool.drop(locked_second[0])

    asyncio.run(run())


def test_claim_pool_lock_all_resources():
    """Lock all resources; a new lock waits until one is dropped."""
    async def run():
        pool: ClaimPool[u32] = ClaimPool[u32].fromList([10, 20])

        c1 = await pool.lock()
        c2 = await pool.lock()

        acquired = []

        async def waiter():
            c = await pool.lock()
            acquired.append(c)

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        assert acquired == []

        pool.drop(c1)
        await task

        assert len(acquired) == 1
        pool.drop(c2)
        pool.drop(acquired[0])

    asyncio.run(run())


def test_claim_pool_lock_filter():
    """Only resources passing the filter predicate are eligible."""
    async def run():
        pool: ClaimPool[u32] = ClaimPool[u32].fromList([1, 2, 3, 4])

        claim = await pool.lock(filter=lambda v, i: v % 2 == 0)
        assert claim.t % 2 == 0
        pool.drop(claim)

    asyncio.run(run())


def test_claim_pool_lock_filter_all_locked():
    """When filtered resources are all locked, waiter unblocks after drop."""
    async def run():
        pool: ClaimPool[u32] = ClaimPool[u32].fromList([1, 2, 3])

        even_claim = await pool.lock(filter=lambda v, i: v % 2 == 0)
        assert even_claim.t == 2

        acquired = []

        async def waiter():
            c = await pool.lock(filter=lambda v, i: v % 2 == 0)
            acquired.append(c)

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        assert acquired == []

        pool.drop(even_claim)
        await task

        assert len(acquired) == 1
        assert acquired[0].t == 2
        pool.drop(acquired[0])

    asyncio.run(run())


def test_claim_pool_share_basic():
    """Multiple share claims on the same resource are allowed."""
    async def run():
        pool: ClaimPool[str] = ClaimPool[str].fromList(["r"])

        s1 = await pool.share()
        s2 = await pool.share()

        assert s1.t == "r"
        assert s2.t == "r"
        assert s1.id == s2.id

        pool.drop(s1)
        pool.drop(s2)

    asyncio.run(run())


def test_claim_pool_share_blocks_lock():
    """A shared resource cannot be locked until all shares are dropped."""
    async def run():
        pool: ClaimPool[str] = ClaimPool[str].fromList(["r"])

        share = await pool.share()

        locked = []

        async def try_lock():
            c = await pool.lock()
            locked.append(c)

        task = asyncio.create_task(try_lock())
        await asyncio.sleep(0)
        assert locked == [], "Lock should wait while resource is shared"

        pool.drop(share)
        await task

        assert len(locked) == 1
        pool.drop(locked[0])

    asyncio.run(run())


def test_claim_pool_share_multiple_then_lock():
    """Lock waits until ALL share holders drop."""
    async def run():
        pool: ClaimPool[str] = ClaimPool[str].fromList(["r"])

        s1 = await pool.share()
        s2 = await pool.share()

        locked = []

        async def try_lock():
            c = await pool.lock()
            locked.append(c)

        task = asyncio.create_task(try_lock())
        await asyncio.sleep(0)
        assert locked == []

        pool.drop(s1)
        await asyncio.sleep(0)
        assert locked == [], "Lock should still wait after first share drop"

        pool.drop(s2)
        await task

        assert len(locked) == 1
        pool.drop(locked[0])

    asyncio.run(run())


def test_claim_pool_drop_multiple_waiters():
    """Multiple waiters are all eventually served after drops."""
    async def run():
        pool: ClaimPool[str] = ClaimPool[str].fromList(["only"])
        c0 = await pool.lock()

        results = []

        async def waiter(tag):
            c = await pool.lock()
            results.append(tag)
            pool.drop(c)

        t1 = asyncio.create_task(waiter("first"))
        t2 = asyncio.create_task(waiter("second"))
        await asyncio.sleep(0)
        assert results == []

        pool.drop(c0)
        await t1
        await t2

        assert sorted(results) == ["first", "second"]

    asyncio.run(run())


def test_claim_pool_claim_id_is_valid_index():
    """claim.id is a valid index into the pool's resource list."""
    async def run():
        pool: ClaimPool[str] = ClaimPool[str].fromList(["x", "y", "z"])
        claim = await pool.lock()
        assert 0 <= claim.id < 3
        assert claim.t in ("x", "y", "z")
        pool.drop(claim)

    asyncio.run(run())


# ---------------------------------------------------------------------------
# ListBufferPool tests (via BufferPool.fromList)
# ---------------------------------------------------------------------------

def test_buffer_pool_get_basic():
    """get() returns an item from the pool."""
    async def run():
        pool: BufferPool[u32] = BufferPool[u32].fromList([10, 20, 30])
        item = await pool.get()
        assert item in (10, 20, 30)

    asyncio.run(run())


def test_buffer_pool_roundrobin():
    """Default selector cycles through items in order."""
    async def run():
        pool: BufferPool[str] = BufferPool[str].fromList(["a", "b", "c"])
        results = [await pool.get() for _ in range(6)]
        assert results == ["a", "b", "c", "a", "b", "c"]

    asyncio.run(run())


def test_buffer_pool_where_filter():
    """where predicate restricts which items are eligible."""
    async def run():
        pool: BufferPool[u32] = BufferPool[u32].fromList([1, 2, 3, 4, 5])
        item = await pool.get(where=lambda v: v % 2 == 0)
        assert item % 2 == 0

    asyncio.run(run())


def test_buffer_pool_where_cycles_filtered():
    """Round-robin selection operates on the filtered subset."""
    async def run():
        pool: BufferPool[u32] = BufferPool[u32].fromList([1, 2, 3, 4])
        evens = [await pool.get(where=lambda v: v % 2 == 0) for _ in range(4)]
        assert evens == [2, 4, 2, 4]

    asyncio.run(run())


def test_buffer_pool_custom_select():
    """A custom select coroutine overrides the default selection."""
    async def run():
        pool: BufferPool[str] = BufferPool[str].fromList(["a", "b", "c"])

        async def always_last(items):
            return items[-1]

        item = await pool.get(select=always_last)
        assert item == "c"

    asyncio.run(run())


def test_buffer_pool_put_unblocks_get():
    """get() on an empty pool blocks until put() supplies an item."""
    async def run():
        pool: BufferPool[u32] = BufferPool[u32].fromList([])

        received = []

        async def getter():
            received.append(await pool.get())

        task = asyncio.create_task(getter())
        await asyncio.sleep(0)
        assert received == [], "get() should be blocked on empty pool"

        pool.put(42)
        await task

        assert received == [42]

    asyncio.run(run())


def test_buffer_pool_put_appends_to_nonempty():
    """put() adds an item that is visible to subsequent get() calls."""
    async def run():
        pool: BufferPool[u32] = BufferPool[u32].fromList([1])
        pool.put(2)
        pool.put(3)

        results = [await pool.get() for _ in range(3)]
        assert sorted(results) == [1, 2, 3]

    asyncio.run(run())


def test_buffer_pool_put_multiple_waiters():
    """Multiple blocked get() calls each unblock when matching items are put."""
    async def run():
        pool: BufferPool[u32] = BufferPool[u32].fromList([])

        received = []

        async def getter():
            received.append(await pool.get())

        t1 = asyncio.create_task(getter())
        t2 = asyncio.create_task(getter())
        await asyncio.sleep(0)
        assert received == []

        pool.put(10)
        pool.put(20)
        await t1
        await t2

        assert sorted(received) == [10, 20]

    asyncio.run(run())


def test_buffer_pool_put_unblocks_where_filter():
    """get(where=...) blocks until put() supplies an item matching the filter."""
    async def run():
        pool: BufferPool[u32] = BufferPool[u32].fromList([1, 3, 5])  # only odds

        received = []

        async def getter():
            received.append(await pool.get(where=lambda v: v % 2 == 0))

        task = asyncio.create_task(getter())
        await asyncio.sleep(0)
        assert received == [], "no even items yet — get() should block"

        pool.put(4)
        await task

        assert received == [4]

    asyncio.run(run())


