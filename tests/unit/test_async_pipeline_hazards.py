"""Phase 3 tests — hazard lock rt: QueueLock, BypassLock, resource protocol.

In the sequential token model each token runs all stages to completion before
the next token starts.  This means prior-token data is always visible when a
later token blocks, so actual asyncio waiting never occurs.  What these tests
verify is that the *protocol* (reserve → block → write → release) executes
without error, returns correct values, and accounts for cycles correctly.
"""

import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import Time, TimeUnit


def run_comp(comp, ns: int):
    asyncio.run(comp.wait(Time(TimeUnit.NS, ns)))


# ---------------------------------------------------------------------------
# PipelineResource creation
# ---------------------------------------------------------------------------

class TestResourceCreation:
    def test_resource_default_queue_lock(self):
        """resource() without lock arg uses QueueLock by default."""
        from zuspec.dataclasses.pipeline_locks import QueueLock
        rf = zdc.pipeline.resource(32)
        assert isinstance(rf.lock, QueueLock)
        assert rf.size == 32

    def test_resource_bypass_lock(self):
        """resource() with BypassLock stores it correctly."""
        from zuspec.dataclasses.pipeline_locks import BypassLock
        rf = zdc.pipeline.resource(16, lock=zdc.BypassLock())
        assert isinstance(rf.lock, BypassLock)

    def test_resource_subscript_returns_proxy(self):
        """rf[addr] returns a _ResourceProxy with correct resource and addr."""
        from zuspec.dataclasses.pipeline_resource import _ResourceProxy
        rf = zdc.pipeline.resource(32)
        proxy = rf[5]
        assert isinstance(proxy, _ResourceProxy)
        assert proxy.resource is rf
        assert proxy.addr == 5


# ---------------------------------------------------------------------------
# QueueLock protocol
# ---------------------------------------------------------------------------

class TestQueueLockProtocol:
    def test_queue_lock_reserve_block_release_no_error(self):
        """Single-token QueueLock protocol completes without error."""
        results = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            rf: object = zdc.field(
                default_factory=lambda: zdc.pipeline.resource(32, lock=zdc.QueueLock())
            )

            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    rd = 5
                    await zdc.pipeline.reserve(self.rf[rd])
                async with zdc.pipeline.stage() as EX:
                    rs1 = 5
                    val = await zdc.pipeline.block(self.rf[rs1])
                    results.append(val)
                    zdc.pipeline.write(self.rf[rd], 42)
                async with zdc.pipeline.stage() as WB:
                    zdc.pipeline.release(self.rf[rd])

        p = Pipe()
        run_comp(p, 30)
        assert len(results) >= 1
        # QueueLock has no bypass — block() returns None
        assert all(v is None for v in results)

    def test_queue_lock_multiple_tokens_no_deadlock(self):
        """Multiple tokens through QueueLock pipeline complete without deadlock."""
        count = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            rf: object = zdc.field(
                default_factory=lambda: zdc.pipeline.resource(32, lock=zdc.QueueLock())
            )

            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    await zdc.pipeline.reserve(self.rf[3])
                async with zdc.pipeline.stage() as EX:
                    await zdc.pipeline.block(self.rf[3])
                    zdc.pipeline.write(self.rf[3], 99)
                async with zdc.pipeline.stage() as WB:
                    zdc.pipeline.release(self.rf[3])
                    count.append(1)

        p = Pipe()
        run_comp(p, 50)
        assert len(count) >= 3

    def test_queue_lock_different_addresses_independent(self):
        """Reservations on different addresses do not interfere."""
        vals = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            rf: object = zdc.field(
                default_factory=lambda: zdc.pipeline.resource(32, lock=zdc.QueueLock())
            )

            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    await zdc.pipeline.reserve(self.rf[1])
                    await zdc.pipeline.reserve(self.rf[2])
                async with zdc.pipeline.stage() as WB:
                    zdc.pipeline.release(self.rf[1])
                    zdc.pipeline.release(self.rf[2])
                    vals.append("ok")

        p = Pipe()
        run_comp(p, 30)
        assert len(vals) >= 2


# ---------------------------------------------------------------------------
# BypassLock protocol
# ---------------------------------------------------------------------------

class TestBypassLockProtocol:
    def test_bypass_lock_block_returns_written_value(self):
        """block() on BypassLock returns the value written by the same token."""
        received = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            rf: object = zdc.field(
                default_factory=lambda: zdc.pipeline.resource(32, lock=zdc.BypassLock())
            )

            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    rd = 7
                    await zdc.pipeline.reserve(self.rf[rd])
                async with zdc.pipeline.stage() as EX:
                    # Write before a later token could block — value goes to bypass buffer
                    zdc.pipeline.write(self.rf[7], 123)
                    # Reading back via block() should immediately return 123
                    val = await zdc.pipeline.block(self.rf[7])
                    received.append(val)
                async with zdc.pipeline.stage() as WB:
                    zdc.pipeline.release(self.rf[7])

        p = Pipe()
        run_comp(p, 30)
        assert len(received) >= 1
        assert all(v == 123 for v in received)

    def test_bypass_lock_block_no_writer_returns_none(self):
        """block() with no outstanding writer returns None immediately."""
        received = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            rf: object = zdc.field(
                default_factory=lambda: zdc.pipeline.resource(32, lock=zdc.BypassLock())
            )

            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as EX:
                    # No reserve() was called — no writers outstanding
                    val = await zdc.pipeline.block(self.rf[4])
                    received.append(val)

        p = Pipe()
        run_comp(p, 20)
        assert len(received) >= 1
        assert all(v is None for v in received)

    def test_bypass_lock_multiple_tokens_independent(self):
        """Each token's reserve/write/release cycle is independent."""
        log = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            rf: object = zdc.field(
                default_factory=lambda: zdc.pipeline.resource(32, lock=zdc.BypassLock())
            )

            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    await zdc.pipeline.reserve(self.rf[0])
                async with zdc.pipeline.stage() as EX:
                    zdc.pipeline.write(self.rf[0], 7)
                async with zdc.pipeline.stage() as WB:
                    zdc.pipeline.release(self.rf[0])
                    log.append("done")

        p = Pipe()
        run_comp(p, 60)
        assert len(log) >= 3


# ---------------------------------------------------------------------------
# acquire() = reserve + block combined
# ---------------------------------------------------------------------------

class TestAcquire:
    def test_acquire_no_error(self):
        """acquire() (reserve+block) completes without error using QueueLock."""
        seen = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            rf: object = zdc.field(
                default_factory=lambda: zdc.pipeline.resource(32, lock=zdc.QueueLock())
            )

            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    await zdc.pipeline.acquire(self.rf[2])
                    seen.append(1)
                async with zdc.pipeline.stage() as WB:
                    zdc.pipeline.release(self.rf[2])

        p = Pipe()
        run_comp(p, 30)
        assert len(seen) >= 2


# ---------------------------------------------------------------------------
# Lock rt unit tests (direct, no component)
# ---------------------------------------------------------------------------

class TestQueueLockRt:
    def test_reserve_and_release_sets_event(self):
        """reserve() adds event; release() signals it."""
        from zuspec.dataclasses.rt.pipeline_locks_rt import QueueLockRt

        async def run():
            q = QueueLockRt()
            await q.reserve(0)
            events = list(q._queues[0])
            assert len(events) == 1
            assert not events[0].is_set()
            q.release(0)
            assert events[0].is_set()
            assert len(q._queues[0]) == 0

        asyncio.run(run())

    def test_block_returns_none(self):
        """block() always returns None (no bypass in QueueLock)."""
        from zuspec.dataclasses.rt.pipeline_locks_rt import QueueLockRt

        async def run():
            q = QueueLockRt()
            result = await q.block(99)
            assert result is None

        asyncio.run(run())

    def test_release_on_empty_queue_is_noop(self):
        """release() on an address with no reservations does not crash."""
        from zuspec.dataclasses.rt.pipeline_locks_rt import QueueLockRt

        async def run():
            q = QueueLockRt()
            q.release(42)  # should not raise

        asyncio.run(run())


class TestBypassLockRt:
    def test_write_then_block_returns_value(self):
        """write() before block() → block returns immediately with the value."""
        from zuspec.dataclasses.rt.pipeline_locks_rt import BypassLockRt

        async def run():
            b = BypassLockRt()
            await b.reserve(1)
            b.write(1, 55)
            val = await b.block(1)
            assert val == 55

        asyncio.run(run())

    def test_block_then_write_resolves_future(self):
        """block() before write() → future resolves when write() is called."""
        from zuspec.dataclasses.rt.pipeline_locks_rt import BypassLockRt

        results = []

        async def run():
            b = BypassLockRt()
            await b.reserve(2)

            async def reader():
                val = await b.block(2)
                results.append(val)

            async def writer():
                await asyncio.sleep(0)  # yield so reader suspends first
                b.write(2, 77)

            await asyncio.gather(reader(), writer())

        asyncio.run(run())
        assert results == [77]

    def test_release_clears_bypass_when_no_writers(self):
        """release() removes bypass entry when writer count reaches zero."""
        from zuspec.dataclasses.rt.pipeline_locks_rt import BypassLockRt

        async def run():
            b = BypassLockRt()
            await b.reserve(3)
            b.write(3, 9)
            assert 3 in b._bypass
            b.release(3)
            assert 3 not in b._bypass

        asyncio.run(run())

    def test_block_no_writer_returns_none(self):
        """block() when no writer is outstanding returns None immediately."""
        from zuspec.dataclasses.rt.pipeline_locks_rt import BypassLockRt

        async def run():
            b = BypassLockRt()
            val = await b.block(5)
            assert val is None

        asyncio.run(run())
