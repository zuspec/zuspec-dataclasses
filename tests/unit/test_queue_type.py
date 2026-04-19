"""Tier 1 tests for zdc.Queue[T] and zdc.queue() (Phase 1/2)."""
import asyncio
import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Basic put/get round-trip
# ---------------------------------------------------------------------------

class TestQueueBasic:
    def test_put_get_roundtrip(self):
        async def run():
            q = zdc.queue(depth=4)
            await q.put(10)
            await q.put(20)
            v1 = await q.get()
            v2 = await q.get()
            assert v1 == 10
            assert v2 == 20

        asyncio.run(run())

    def test_fifo_ordering(self):
        async def run():
            q = zdc.queue(depth=8)
            for i in range(5):
                await q.put(i)
            results = [await q.get() for _ in range(5)]
            assert results == list(range(5))

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Depth limit / blocking
# ---------------------------------------------------------------------------

class TestQueueDepth:
    def test_full_blocks_on_overflow(self):
        """put() blocks when queue is full; get() unblocks it."""
        async def run():
            q = zdc.queue(depth=1)
            await q.put("first")
            assert q.full()

            unblocked = []

            async def producer():
                await q.put("second")   # blocks until consumer calls get()
                unblocked.append(True)

            asyncio.create_task(producer())
            await asyncio.sleep(0)
            assert not unblocked          # still blocked

            _ = await q.get()            # free one slot
            await asyncio.sleep(0)
            assert unblocked             # now unblocked

        asyncio.run(run())

    def test_get_blocks_on_empty(self):
        """get() suspends until put() is called."""
        async def run():
            q = zdc.queue(depth=2)
            received = []

            async def consumer():
                v = await q.get()
                received.append(v)

            asyncio.create_task(consumer())
            await asyncio.sleep(0)
            assert not received

            await q.put(42)
            await asyncio.sleep(0)
            assert received == [42]

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Status predicates
# ---------------------------------------------------------------------------

class TestQueuePredicates:
    def test_empty_and_full(self):
        async def run():
            q = zdc.queue(depth=2)
            assert q.empty()
            assert not q.full()
            assert q.qsize() == 0

            await q.put(1)
            assert not q.empty()
            assert not q.full()
            assert q.qsize() == 1

            await q.put(2)
            assert not q.empty()
            assert q.full()
            assert q.qsize() == 2

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Factory validation
# ---------------------------------------------------------------------------

class TestQueueFactory:
    def test_depth_zero_raises(self):
        with pytest.raises(ValueError, match="depth"):
            zdc.queue(depth=0)

    def test_depth_negative_raises(self):
        with pytest.raises(ValueError, match="depth"):
            zdc.queue(depth=-1)

    def test_returns_queue_instance(self):
        q = zdc.queue(depth=4)
        assert hasattr(q, "put")
        assert hasattr(q, "get")
        assert hasattr(q, "qsize")
