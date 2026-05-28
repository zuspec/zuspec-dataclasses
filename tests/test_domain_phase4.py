"""Phase 4 — @zdc.sync domain-aware resolution tests.

Verifies that:
- Bare ``@zdc.sync`` fires on any domain tick (default inherited domain).
- ``@zdc.sync(domain=lambda s: s.fast_clk)`` fires *only* when the named
  domain ticks, not when the default domain ticks.
- Multiple named domains are independently controllable.
"""

import asyncio
import pytest
import zuspec.dataclasses as zdc
from typing import ClassVar


# ---------------------------------------------------------------------------
# Component definitions (must be module-level for inspect.getsource)
# ---------------------------------------------------------------------------

@zdc.dataclass
class SlowFastDomain(zdc.SyncComponent):
    """Two-domain component: default (slow) and explicit fast_clk."""
    reset_domain = zdc.ResetDomain(style="none")
    fast_clk: ClassVar[zdc.ClockDomain] = zdc.ClockDomain()

    slow_count: zdc.bit32 = zdc.output(reset=0)
    fast_count: zdc.bit32 = zdc.output(reset=0)

    @zdc.sync
    def _slow(self):
        self.slow_count = self.slow_count + 1

    @zdc.sync(domain=lambda s: s.fast_clk)
    def _fast(self):
        self.fast_count = self.fast_count + 1


@zdc.dataclass
class ThreeDomainComp(zdc.SyncComponent):
    """Three domains: default, d1, d2."""
    reset_domain = zdc.ResetDomain(style="none")
    d1: ClassVar[zdc.ClockDomain] = zdc.ClockDomain()
    d2: ClassVar[zdc.ClockDomain] = zdc.ClockDomain()

    default_count: zdc.bit32 = zdc.output(reset=0)
    d1_count: zdc.bit32 = zdc.output(reset=0)
    d2_count: zdc.bit32 = zdc.output(reset=0)

    @zdc.sync
    def _default(self):
        self.default_count = self.default_count + 1

    @zdc.sync(domain=lambda s: s.d1)
    def _d1(self):
        self.d1_count = self.d1_count + 1

    @zdc.sync(domain=lambda s: s.d2)
    def _d2(self):
        self.d2_count = self.d2_count + 1


@zdc.dataclass
class BareOnlyComp(zdc.SyncComponent):
    """Component with only bare @zdc.sync — must still fire normally."""
    reset_domain = zdc.ResetDomain(style="none")
    count: zdc.bit32 = zdc.output(reset=0)

    @zdc.sync
    def _inc(self):
        self.count = self.count + 1


# ---------------------------------------------------------------------------
# Test: SimDomain exposes named domain accessors
# ---------------------------------------------------------------------------

class TestSimDomainAccessors:
    def test_default_domain_exists(self):
        async def _run():
            async with zdc.simulate(SlowFastDomain) as d:
                assert hasattr(d, 'domain')

        asyncio.run(_run())

    def test_named_domain_accessor_created(self):
        async def _run():
            async with zdc.simulate(SlowFastDomain) as d:
                assert hasattr(d, 'fast_clk_sim'), \
                    "Expected 'fast_clk_sim' accessor for named ClockDomain 'fast_clk'"

        asyncio.run(_run())

    def test_named_domains_have_distinct_domain_obj(self):
        async def _run():
            async with zdc.simulate(SlowFastDomain) as d:
                assert d.domain._domain_obj is not d.fast_clk_sim._domain_obj

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: domain= filtering on sync methods
# ---------------------------------------------------------------------------

class TestDomainFilteredSync:
    def test_bare_sync_fires_on_default_tick(self):
        async def _run():
            async with zdc.simulate(BareOnlyComp) as d:
                await d.domain.tick(3)
                assert d.count == 3

        asyncio.run(_run())

    def test_slow_fires_on_default_tick_not_fast(self):
        async def _run():
            async with zdc.simulate(SlowFastDomain) as d:
                await d.domain.tick(4)
                assert d.slow_count == 4
                assert d.fast_count == 0, \
                    "fast_count should not increment on default domain tick"

        asyncio.run(_run())

    def test_fast_fires_on_fast_tick_not_slow(self):
        async def _run():
            async with zdc.simulate(SlowFastDomain) as d:
                await d.fast_clk_sim.tick(5)
                assert d.fast_count == 5
                assert d.slow_count == 0, \
                    "slow_count should not increment on fast_clk domain tick"

        asyncio.run(_run())

    def test_both_domains_independent(self):
        async def _run():
            async with zdc.simulate(SlowFastDomain) as d:
                await d.domain.tick(2)
                await d.fast_clk_sim.tick(3)
                assert d.slow_count == 2
                assert d.fast_count == 3

        asyncio.run(_run())

    def test_interleaved_ticks(self):
        async def _run():
            async with zdc.simulate(SlowFastDomain) as d:
                await d.domain.tick(1)
                await d.fast_clk_sim.tick(1)
                await d.domain.tick(1)
                await d.fast_clk_sim.tick(2)
                assert d.slow_count == 2
                assert d.fast_count == 3

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: three independent domains
# ---------------------------------------------------------------------------

class TestThreeDomains:
    def test_three_named_domain_accessors(self):
        async def _run():
            async with zdc.simulate(ThreeDomainComp) as d:
                assert hasattr(d, 'domain')
                assert hasattr(d, 'd1_sim')
                assert hasattr(d, 'd2_sim')

        asyncio.run(_run())

    def test_each_domain_only_fires_own_method(self):
        async def _run():
            async with zdc.simulate(ThreeDomainComp) as d:
                await d.domain.tick(1)
                assert d.default_count == 1
                assert d.d1_count == 0
                assert d.d2_count == 0

                await d.d1_sim.tick(2)
                assert d.default_count == 1
                assert d.d1_count == 2
                assert d.d2_count == 0

                await d.d2_sim.tick(3)
                assert d.default_count == 1
                assert d.d1_count == 2
                assert d.d2_count == 3

        asyncio.run(_run())
