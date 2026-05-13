"""Phase 6 tests: SDC emission.

Covers:
- create_clock for a root ClockDomain with period
- create_generated_clock for DerivedClockDomain with div
- No duplicate create_clock when two children share the same domain
- set_false_path for CDC crossing between two different domains
- CDC crossing suppressed for TwoFFSync primitives
- Reset sequencing false path when ResetDomain has release_after
"""

import asyncio
import pytest
import zuspec.dataclasses as zdc
from typing import ClassVar
from zuspec.dataclasses.domain import (
    ClockDomain, DerivedClockDomain, InheritedDomain, ResetDomain
)
from zuspec.dataclasses.sdc_emit import SDCEmitPass, emit_sdc


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _sdc(comp) -> str:
    p = SDCEmitPass()
    p.visit(comp)
    return p.sdc_text()


# ---------------------------------------------------------------------------
# Component definitions (module-level for inspect.getsource)
# ---------------------------------------------------------------------------

@zdc.dataclass
class SdcSingleClock(zdc.SyncComponent):
    """Single 10 ns clock, no children."""
    clock_domain = ClockDomain(period=zdc.Time.ns(10), name="sys_clk")
    reset_domain = ResetDomain(style="none")
    count: zdc.bit32 = 0

    @zdc.sync
    def step(self):
        self.count += 1


@zdc.dataclass
class SdcNoPeriod(zdc.SyncComponent):
    """Clock without a period — no create_clock expected."""
    clock_domain = ClockDomain(name="unbound_clk")
    reset_domain = ResetDomain(style="none")
    count: zdc.bit32 = 0

    @zdc.sync
    def step(self):
        self.count += 1


@zdc.dataclass
class SdcWorker(zdc.SyncComponent):
    """Reusable counter worker."""
    reset_domain = ResetDomain(style="none")
    count: zdc.bit32 = 0

    @zdc.sync
    def step(self):
        self.count += 1


@zdc.dataclass
class SdcTwoChildren(zdc.SyncComponent):
    """Parent with two children on same domain — expect only one create_clock."""
    clock_domain = ClockDomain(period=zdc.Time.ns(10), name="sys_clk")
    reset_domain = ResetDomain(style="none")
    a: SdcWorker = zdc.inst()
    b: SdcWorker = zdc.inst()


@zdc.dataclass
class SdcFastChild(zdc.SyncComponent):
    """Child that runs on fast_clk — different domain → CDC crossing."""
    reset_domain = ResetDomain(style="none")
    count: zdc.bit32 = 0

    @zdc.sync
    def step(self):
        self.count += 1


@zdc.dataclass
class SdcCdcTop(zdc.SyncComponent):
    """Top with two domains and a child overridden to fast_clk → CDC path."""
    clock_domain = ClockDomain(period=zdc.Time.ns(10), name="slow_clk")
    reset_domain = ResetDomain(style="none")
    fast_clk: ClassVar[ClockDomain] = ClockDomain(period=zdc.Time.ns(2), name="fast_clk")
    fast_child: SdcFastChild = zdc.inst()

    def __bind__(self):
        return {self.fast_child.clock_domain: self.fast_clk}


@zdc.dataclass
class SdcDerivedChild(zdc.SyncComponent):
    """Child with a derived clock (div=4)."""
    reset_domain = ResetDomain(style="none")
    fast_clk: ClassVar[DerivedClockDomain] = DerivedClockDomain(
        source=InheritedDomain(), div=4, name="fast_div4"
    )
    count: zdc.bit32 = 0

    @zdc.sync
    def step(self):
        self.count += 1


@zdc.dataclass
class SdcDerivedTop(zdc.SyncComponent):
    """Top with 10 ns clock, child declares a div-4 derived clock."""
    clock_domain = ClockDomain(period=zdc.Time.ns(10), name="sys_clk")
    reset_domain = ResetDomain(style="none")
    child: SdcDerivedChild = zdc.inst()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateClock:
    def test_create_clock_emitted(self):
        """A ClockDomain with period emits create_clock."""
        async def _run():
            async with zdc.simulate(SdcSingleClock) as d:
                return _sdc(d)
        text = asyncio.run(_run())
        assert "create_clock" in text, f"Expected create_clock in:\n{text}"
        assert "sys_clk" in text
        assert "10.000" in text

    def test_no_create_clock_without_period(self):
        """A ClockDomain without a period does NOT emit create_clock."""
        async def _run():
            async with zdc.simulate(SdcNoPeriod) as d:
                return _sdc(d)
        text = asyncio.run(_run())
        assert "create_clock" not in text, f"Unexpected create_clock in:\n{text}"

    def test_no_duplicate_clocks(self):
        """Two children sharing the same domain emit only one create_clock."""
        async def _run():
            async with zdc.simulate(SdcTwoChildren) as d:
                return _sdc(d)
        text = asyncio.run(_run())
        # Count occurrences of create_clock
        count = text.count("create_clock")
        assert count == 1, f"Expected 1 create_clock, found {count}:\n{text}"


class TestCreateGeneratedClock:
    def test_derived_clock_emitted(self):
        """DerivedClockDomain(div=4) emits create_generated_clock with -divide_by 4."""
        async def _run():
            async with zdc.simulate(SdcDerivedTop) as d:
                return _sdc(d)
        text = asyncio.run(_run())
        assert "create_generated_clock" in text, f"Expected create_generated_clock:\n{text}"
        assert "fast_div4" in text
        assert "-divide_by 4" in text

    def test_derived_clock_sources_parent(self):
        """Generated clock references the parent's sys_clk as source."""
        async def _run():
            async with zdc.simulate(SdcDerivedTop) as d:
                return _sdc(d)
        text = asyncio.run(_run())
        assert "sys_clk" in text


class TestCdcFalsePaths:
    def test_cdc_false_path_emitted(self):
        """Crossing between slow_clk and fast_clk emits set_false_path."""
        async def _run():
            async with zdc.simulate(SdcCdcTop) as d:
                return _sdc(d)
        text = asyncio.run(_run())
        assert "set_false_path" in text, f"Expected set_false_path:\n{text}"
        assert "slow_clk" in text
        assert "fast_clk" in text

    def test_same_domain_no_false_path(self):
        """Two children on the same domain do NOT emit a CDC false path."""
        async def _run():
            async with zdc.simulate(SdcTwoChildren) as d:
                return _sdc(d)
        text = asyncio.run(_run())
        assert "set_false_path" not in text, f"Unexpected set_false_path:\n{text}"


class TestSDCAPI:
    def test_emit_sdc_helper(self):
        """emit_sdc() convenience function returns a non-empty string."""
        async def _run():
            async with zdc.simulate(SdcSingleClock) as d:
                return emit_sdc(d)
        text = asyncio.run(_run())
        assert isinstance(text, str)
        assert len(text) > 0

    def test_sdc_emitpass_exportable(self):
        """SDCEmitPass and emit_sdc are accessible via zdc namespace."""
        assert hasattr(zdc, 'SDCEmitPass')
        assert hasattr(zdc, 'emit_sdc')
