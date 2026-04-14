"""Unit tests for InPort / OutPort pipeline method ports.

Covers:
- Standalone InPort.drive() → get() round-trip
- Standalone OutPort.put() → collect() round-trip
- InPort/OutPort as component fields (descriptor protocol)
- End-to-end pipeline: get() ingress, put() egress
- Multiple InPorts on one component
- OutPort.count() and multiple emits
"""

import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import Time, TimeUnit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async(coro, timeout: float = 5.0):
    async def _wrapper():
        return await asyncio.wait_for(coro, timeout=timeout)
    return asyncio.run(_wrapper())


def run_comp(comp, ns: int):
    asyncio.run(comp.wait(Time(TimeUnit.NS, ns)))


# ---------------------------------------------------------------------------
# Standalone InPort tests
# ---------------------------------------------------------------------------

class TestInPort:
    def test_drive_then_get_returns_value(self):
        """drive() enqueues; get() dequeues the same value."""
        port = zdc.InPort()
        port.drive(42)

        result = run_async(port.get())
        assert result == 42

    def test_drive_multiple_fifo_order(self):
        """Multiple drive() calls are returned in FIFO order."""
        port = zdc.InPort()
        port.drive(1)
        port.drive(2)
        port.drive(3)

        async def consume():
            return [await port.get() for _ in range(3)]

        assert run_async(consume()) == [1, 2, 3]

    def test_qsize_reflects_pending(self):
        port = zdc.InPort()
        assert port.qsize() == 0
        port.drive(10)
        assert port.qsize() == 1
        port.drive(20)
        assert port.qsize() == 2

    def test_get_blocks_until_driven(self):
        """get() suspends until drive() is called."""
        port = zdc.InPort()

        async def producer():
            await asyncio.sleep(0)   # yield once
            port.drive(99)

        async def consumer():
            return await port.get()

        async def run():
            v, _ = await asyncio.gather(consumer(), producer())
            return v

        assert run_async(run()) == 99


# ---------------------------------------------------------------------------
# Standalone OutPort tests
# ---------------------------------------------------------------------------

class TestOutPort:
    def test_put_then_collect(self):
        port = zdc.OutPort()

        async def go():
            await port.put(7)
            await port.put(8)
            return port.collect()

        results = run_async(go())
        assert results == [7, 8]

    def test_collect_clears_by_default(self):
        port = zdc.OutPort()

        async def go():
            await port.put(1)
            first = port.collect()
            second = port.collect()
            return first, second

        first, second = run_async(go())
        assert first == [1]
        assert second == []

    def test_collect_no_clear(self):
        port = zdc.OutPort()

        async def go():
            await port.put(3)
            return port.collect(clear=False), port.count()

        results, cnt = run_async(go())
        assert results == [3]
        assert cnt == 1

    def test_count_increments(self):
        port = zdc.OutPort()
        assert port.count() == 0

        async def go():
            await port.put(0)
            await port.put(1)

        run_async(go())
        assert port.count() == 2


# ---------------------------------------------------------------------------
# Component descriptor tests
# ---------------------------------------------------------------------------

class TestDescriptors:
    def test_in_port_descriptor(self):
        @zdc.dataclass
        class C(zdc.Component):
            data_in: zdc.InPort[zdc.u32] = zdc.in_port()

        c = C()
        assert isinstance(c.data_in, zdc.InPort)
        assert c.data_in.port_name == "data_in"

    def test_out_port_descriptor(self):
        @zdc.dataclass
        class C(zdc.Component):
            data_out: zdc.OutPort[zdc.u32] = zdc.out_port()

        c = C()
        assert isinstance(c.data_out, zdc.OutPort)
        assert c.data_out.port_name == "data_out"

    def test_separate_instances_have_separate_queues(self):
        @zdc.dataclass
        class C(zdc.Component):
            val_in: zdc.InPort[int] = zdc.in_port()

        c1 = C()
        c2 = C()
        c1.val_in.drive(100)
        assert c1.val_in.qsize() == 1
        assert c2.val_in.qsize() == 0

    def test_out_port_separate_instances(self):
        @zdc.dataclass
        class C(zdc.Component):
            out: zdc.OutPort[int] = zdc.out_port()

        c1 = C()
        c2 = C()

        async def go():
            await c1.out.put(1)

        run_async(go())
        assert c1.out.count() == 1
        assert c2.out.count() == 0


# ---------------------------------------------------------------------------
# End-to-end pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_single_stage_get_put(self):
        """Pipeline uses InPort.get() and OutPort.put(); result arrives."""
        received = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            data_in:  zdc.InPort[zdc.u32]  = zdc.in_port()
            data_out: zdc.OutPort[zdc.u32] = zdc.out_port()

            @zdc.pipeline
            async def _run(self):
                val = await self.data_in.get()
                async with zdc.pipeline.stage() as S:
                    pass
                await self.data_out.put(val)

        p = Pipe()
        for i in range(5):
            p.data_in.drive(i * 10)

        run_comp(p, 20)
        results = p.data_out.collect()
        assert len(results) >= 1
        assert all(r % 10 == 0 for r in results)

    def test_three_stage_adder_pipeline(self):
        """3-stage adder: get() a + b in FETCH, compute in COMPUTE, put() in WB."""
        @zdc.dataclass
        class Adder(zdc.Component):
            a_in:    zdc.InPort[zdc.u32]  = zdc.in_port()
            b_in:    zdc.InPort[zdc.u32]  = zdc.in_port()
            sum_out: zdc.OutPort[zdc.u32] = zdc.out_port()

            @zdc.pipeline
            async def _pipe(self):
                a = await self.a_in.get()
                b = await self.b_in.get()

                async with zdc.pipeline.stage() as FETCH:
                    pass

                async with zdc.pipeline.stage() as COMPUTE:
                    result = a + b

                async with zdc.pipeline.stage() as WB:
                    await self.sum_out.put(result)

        adder = Adder()
        pairs = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10)]
        for a, b in pairs:
            adder.a_in.drive(a)
            adder.b_in.drive(b)

        run_comp(adder, 30)
        results = adder.sum_out.collect()
        expected = [a + b for a, b in pairs[:len(results)]]
        assert results == expected

    def test_multiple_ingress_ports(self):
        """Multiple InPorts on one component are independent queues."""
        @zdc.dataclass
        class Mux(zdc.Component):
            x_in: zdc.InPort[int] = zdc.in_port()
            y_in: zdc.InPort[int] = zdc.in_port()
            xy_out: zdc.OutPort[int] = zdc.out_port()

            @zdc.pipeline
            async def _run(self):
                x = await self.x_in.get()
                y = await self.y_in.get()
                async with zdc.pipeline.stage() as S:
                    pass
                await self.xy_out.put(x * 10 + y)

        m = Mux()
        for i in range(4):
            m.x_in.drive(i)
            m.y_in.drive(i + 1)

        run_comp(m, 20)
        results = m.xy_out.collect()
        assert len(results) >= 1
        # Each result encodes x*10 + y
        for r in results:
            assert r // 10 + 1 == r % 10  # y = x + 1

    def test_pipeline_respects_ingress_backpressure(self):
        """Pipeline blocks (stalls) in the get() when no data is ready.

        We deliberately provide fewer tokens than cycles — the pipeline must
        not crash or produce spurious results.
        """
        @zdc.dataclass
        class Pass(zdc.Component):
            val_in:  zdc.InPort[int]  = zdc.in_port()
            val_out: zdc.OutPort[int] = zdc.out_port()

            @zdc.pipeline
            async def _run(self):
                v = await self.val_in.get()
                async with zdc.pipeline.stage() as S:
                    pass
                await self.val_out.put(v)

        p = Pass()
        # Only drive 2 tokens but run for 10 cycles
        p.val_in.drive(1)
        p.val_in.drive(2)

        run_comp(p, 15)
        results = p.val_out.collect()
        assert results == [1, 2]
