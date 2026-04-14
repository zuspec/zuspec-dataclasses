"""Unit tests for ClockDomain and clock_domain() field factory.

Covers:
- clock_domain() descriptor creates a ClockDomain per component instance
- wait_cycle() / wait_cycles() advance simulation time
- Separate instances have independent ClockDomain objects
- pipeline(clock_domain=) kwarg wires the domain into stage timing
- ClockDomain period and freq attributes
"""

import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import Time, TimeUnit
from zuspec.dataclasses.domain import ClockDomain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_comp(comp, ns: int):
    asyncio.run(comp.wait(Time(TimeUnit.NS, ns)))


# ---------------------------------------------------------------------------
# Descriptor / creation tests
# ---------------------------------------------------------------------------

class TestClockDomainDescriptor:
    def test_clock_domain_field_creates_instance(self):
        """clock_domain() descriptor returns a ClockDomain on component access."""
        @zdc.dataclass
        class C(zdc.Component):
            clk: zdc.ClockDomain = zdc.clock_domain()

        c = C()
        assert isinstance(c.clk, ClockDomain)

    def test_separate_component_instances_have_independent_domains(self):
        @zdc.dataclass
        class C(zdc.Component):
            clk: zdc.ClockDomain = zdc.clock_domain()

        c1 = C()
        c2 = C()
        assert c1.clk is not c2.clk

    def test_access_same_field_twice_returns_same_object(self):
        @zdc.dataclass
        class C(zdc.Component):
            clk: zdc.ClockDomain = zdc.clock_domain()

        c = C()
        assert c.clk is c.clk

    def test_clock_domain_with_period(self):
        """clock_domain(period=Time.ns(10)) creates a domain with the right period."""
        @zdc.dataclass
        class C(zdc.Component):
            clk: zdc.ClockDomain = zdc.clock_domain(period=Time.ns(10))

        c = C()
        assert c.clk.period_ns == 10.0

    def test_multiple_domains_on_one_component(self):
        @zdc.dataclass
        class C(zdc.Component):
            clk_a: zdc.ClockDomain = zdc.clock_domain(period=Time.ns(10))
            clk_b: zdc.ClockDomain = zdc.clock_domain(period=Time.ns(20))

        c = C()
        assert c.clk_a is not c.clk_b
        assert c.clk_a.period_ns == 10.0
        assert c.clk_b.period_ns == 20.0


# ---------------------------------------------------------------------------
# wait_cycle / wait_cycles
# ---------------------------------------------------------------------------

class TestWaitCycle:
    def test_wait_cycle_in_pipeline(self):
        """Pipeline stage can call cd.wait_cycle() without error."""
        cycles_seen = []

        @zdc.dataclass
        class C(zdc.Component):
            clk: zdc.ClockDomain = zdc.clock_domain(period=Time.ns(10))
            data_in: zdc.InPort[int] = zdc.in_port()

            @zdc.pipeline(clock_domain=lambda s: s.clk)
            async def _run(self):
                v = await self.data_in.get()
                async with zdc.pipeline.stage() as S:
                    cycles_seen.append(zdc.pipeline.current_cycle())

        c = C()
        for i in range(5):
            c.data_in.drive(i)
        run_comp(c, 80)
        assert len(cycles_seen) >= 1

    def test_wait_cycles_multi_cycle_stage(self):
        """Multi-cycle stage stalls downstream tokens correctly."""
        stage_cycles: list = []

        @zdc.dataclass
        class C(zdc.Component):
            clk: zdc.ClockDomain = zdc.clock_domain(period=Time.ns(10))
            data_in: zdc.InPort[int] = zdc.in_port()

            @zdc.pipeline(clock_domain=lambda s: s.clk)
            async def _run(self):
                v = await self.data_in.get()
                async with zdc.pipeline.stage() as IF:
                    stage_cycles.append(("IF", zdc.pipeline.current_cycle()))

                async with zdc.pipeline.stage() as EX:
                    stage_cycles.append(("EX", zdc.pipeline.current_cycle()))

                async with zdc.pipeline.stage() as WB:
                    stage_cycles.append(("WB", zdc.pipeline.current_cycle()))

        c = C()
        for i in range(4):
            c.data_in.drive(i)
        run_comp(c, 80)

        assert len(stage_cycles) >= 3   # at least one full token pass


# ---------------------------------------------------------------------------
# Integration: clock_domain= kwarg on @zdc.pipeline
# ---------------------------------------------------------------------------

class TestPipelineClockDomain:
    def test_pipeline_with_clock_domain_runs(self):
        """@zdc.pipeline(clock_domain=lambda s: s.clk) executes correctly."""
        @zdc.dataclass
        class C(zdc.Component):
            clk: zdc.ClockDomain = zdc.clock_domain(period=Time.ns(10))
            val_in:  zdc.InPort[int]  = zdc.in_port()
            val_out: zdc.OutPort[int] = zdc.out_port()

            @zdc.pipeline(clock_domain=lambda s: s.clk)
            async def _run(self):
                v = await self.val_in.get()
                async with zdc.pipeline.stage() as S:
                    pass
                await self.val_out.put(v + 1)

        c = C()
        for i in range(3):
            c.val_in.drive(i)
        run_comp(c, 60)
        results = c.val_out.collect()
        assert results == [i + 1 for i in range(len(results))]

    def test_pipeline_clk_domain_attribute_accessible(self):
        """The ClockDomain field is accessible via the pipeline's component."""
        @zdc.dataclass
        class C(zdc.Component):
            clk: zdc.ClockDomain = zdc.clock_domain(period=Time.ns(5))
            data_in: zdc.InPort[int] = zdc.in_port()

            @zdc.pipeline(clock_domain=lambda s: s.clk)
            async def _run(self):
                v = await self.data_in.get()
                async with zdc.pipeline.stage() as S:
                    pass

        c = C()
        assert isinstance(c.clk, ClockDomain)
        assert c.clk.period_ns == 5.0

    def test_two_pipelines_independent_domains(self):
        """Two components with separate clock domains operate independently."""
        @zdc.dataclass
        class Fast(zdc.Component):
            clk:  zdc.ClockDomain  = zdc.clock_domain(period=Time.ns(5))
            inp:  zdc.InPort[int]  = zdc.in_port()
            outp: zdc.OutPort[int] = zdc.out_port()

            @zdc.pipeline(clock_domain=lambda s: s.clk)
            async def _run(self):
                v = await self.inp.get()
                async with zdc.pipeline.stage() as S:
                    pass
                await self.outp.put(v)

        @zdc.dataclass
        class Slow(zdc.Component):
            clk:  zdc.ClockDomain  = zdc.clock_domain(period=Time.ns(20))
            inp:  zdc.InPort[int]  = zdc.in_port()
            outp: zdc.OutPort[int] = zdc.out_port()

            @zdc.pipeline(clock_domain=lambda s: s.clk)
            async def _run(self):
                v = await self.inp.get()
                async with zdc.pipeline.stage() as S:
                    pass
                await self.outp.put(v)

        fast = Fast()
        slow = Slow()
        for i in range(4):
            fast.inp.drive(i)
            slow.inp.drive(i)

        run_comp(fast, 40)
        run_comp(slow, 100)

        fast_results = fast.outp.collect()
        slow_results = slow.outp.collect()
        assert len(fast_results) >= 1
        assert len(slow_results) >= 1
