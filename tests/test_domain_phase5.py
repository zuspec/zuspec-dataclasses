"""Phase 5 tests: __bind__ domain tuple support.

Covers:
- Overriding a child component's clock domain via __bind__ at elaboration time
- Overriding a child component's reset domain via __bind__
- Propagation respects the override: only the matching SimDomain ticks the child
- Children without override still follow parent domain
"""

import asyncio
import pytest
import zuspec.dataclasses as zdc
from typing import ClassVar
from zuspec.dataclasses.domain import ClockDomain, ResetDomain


# ---------------------------------------------------------------------------
# Component definitions at module level (inspect.getsource requirement)
# ---------------------------------------------------------------------------

@zdc.dataclass
class P5Child(zdc.SyncComponent):
    """Simple counter used as a child component in Phase 5 tests."""
    reset_domain = ResetDomain(style="none")
    count: zdc.bit32 = 0

    @zdc.sync
    def step(self):
        self.count += 1


@zdc.dataclass
class P5TopWithOverride(zdc.SyncComponent):
    """Parent with fast_clk; child is bound to fast_clk domain."""
    reset_domain = ResetDomain(style="none")
    fast_clk: ClassVar[ClockDomain] = ClockDomain()
    child: P5Child = zdc.inst()

    def __bind__(self):
        return {
            self.child.clock_domain: self.fast_clk,
        }


@zdc.dataclass
class P5TopNoOverride(zdc.SyncComponent):
    """Parent with fast_clk; child is NOT bound — inherits default domain."""
    reset_domain = ResetDomain(style="none")
    fast_clk: ClassVar[ClockDomain] = ClockDomain()
    child: P5Child = zdc.inst()


@zdc.dataclass
class P5SlowChild(zdc.SyncComponent):
    """Child that stays on the default (slow) domain."""
    reset_domain = ResetDomain(style="none")
    count: zdc.bit32 = 0

    @zdc.sync
    def step(self):
        self.count += 1


@zdc.dataclass
class P5FastChild(zdc.SyncComponent):
    """Child that is overridden to run on the fast domain."""
    reset_domain = ResetDomain(style="none")
    count: zdc.bit32 = 0

    @zdc.sync
    def step(self):
        self.count += 1


@zdc.dataclass
class P5TwoChildTop(zdc.SyncComponent):
    """Top with two children: slow stays on default, fast is overridden."""
    reset_domain = ResetDomain(style="none")
    fast_clk: ClassVar[ClockDomain] = ClockDomain()
    slow_child: P5SlowChild = zdc.inst()
    fast_child: P5FastChild = zdc.inst()

    def __bind__(self):
        return {
            self.fast_child.clock_domain: self.fast_clk,
        }


@zdc.dataclass
class P5Worker(zdc.SyncComponent):
    """Generic counter worker for mixed-override test."""
    reset_domain = ResetDomain(style="none")
    count: zdc.bit32 = 0

    @zdc.sync
    def step(self):
        self.count += 1


@zdc.dataclass
class P5ThreeChildTop(zdc.SyncComponent):
    """Three children: a=default, b=fast, c=fast."""
    reset_domain = ResetDomain(style="none")
    fast_clk: ClassVar[ClockDomain] = ClockDomain()
    a: P5Worker = zdc.inst()
    b: P5Worker = zdc.inst()
    c: P5Worker = zdc.inst()

    def __bind__(self):
        return {
            self.b.clock_domain: self.fast_clk,
            self.c.clock_domain: self.fast_clk,
        }


@zdc.dataclass
class P5ResetOverrideTop(zdc.SyncComponent):
    """Parent that overrides a child's reset_domain via __bind__."""
    reset_domain = ResetDomain(style="none")
    pwr_rst: ClassVar[ResetDomain] = ResetDomain()
    child: P5Child = zdc.inst()

    def __bind__(self):
        return {
            self.child.reset_domain: self.pwr_rst,
        }


# ---------------------------------------------------------------------------
# Tests: domain override via __bind__ sets _zdc_resolved_* on child
# ---------------------------------------------------------------------------

class TestDomainOverrideViaBind:
    """Overriding a child's clock_domain via __bind__ applies at elaboration."""

    def test_child_resolved_domain_changes(self):
        """After override, child._zdc_resolved_clock_domain == parent.fast_clk."""
        async def _run():
            async with zdc.simulate(P5TopWithOverride) as d:
                assert d.child._zdc_resolved_clock_domain is d.fast_clk, \
                    f"Expected child domain = fast_clk, got {d.child._zdc_resolved_clock_domain!r}"
        asyncio.run(_run())

    def test_default_child_unchanged(self):
        """A child without override does NOT get the fast_clk as resolved domain."""
        async def _run():
            async with zdc.simulate(P5TopNoOverride) as d:
                child_resolved = d.child.__dict__.get('_zdc_resolved_clock_domain')
                assert child_resolved is not d.fast_clk, \
                    "Un-overridden child should not have fast_clk as resolved domain"
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Tests: propagation filtering respects override
# ---------------------------------------------------------------------------

class TestPropagationFilter:
    """domain_clock_edge propagation only reaches children matching calling_domain."""

    def test_fast_child_only_on_fast_tick(self):
        """Child with fast_clk override only ticks on fast_clk domain edge."""
        async def _run():
            async with zdc.simulate(P5TwoChildTop) as d:
                # Default (slow) domain: 2 ticks
                await d.domain.tick(2)
                slow_after_slow = d.slow_child.count
                fast_after_slow_only = d.fast_child.count

                # Fast domain: 3 ticks
                await d.fast_clk_sim.tick(3)
                slow_after_fast = d.slow_child.count
                fast_after_fast = d.fast_child.count

                return slow_after_slow, fast_after_slow_only, slow_after_fast, fast_after_fast

        ss, fso, saf, faf = asyncio.run(_run())
        assert ss == 2, f"slow_child after 2 slow ticks: expected 2, got {ss}"
        assert fso == 0, f"fast_child after slow ticks only: expected 0, got {fso}"
        assert saf == 2, f"slow_child after fast ticks: should not increase, got {saf}"
        assert faf == 3, f"fast_child after 3 fast ticks: expected 3, got {faf}"

    def test_slow_child_not_on_fast_tick(self):
        """Default-domain child does NOT tick when fast_clk ticks."""
        async def _run():
            async with zdc.simulate(P5TwoChildTop) as d:
                await d.fast_clk_sim.tick(5)
                return d.slow_child.count, d.fast_child.count

        slow, fast = asyncio.run(_run())
        assert slow == 0, f"slow_child should not tick on fast domain, got {slow}"
        assert fast == 5, f"fast_child should tick 5 times, got {fast}"


# ---------------------------------------------------------------------------
# Tests: reset domain override
# ---------------------------------------------------------------------------

class TestResetDomainOverride:
    """Overriding reset_domain via __bind__ updates _zdc_resolved_reset_domain."""

    def test_reset_domain_override(self):
        """Child gets a different reset domain after __bind__ override."""
        async def _run():
            async with zdc.simulate(P5ResetOverrideTop) as d:
                assert d.child._zdc_resolved_reset_domain is d.pwr_rst, \
                    f"Expected child reset domain = pwr_rst, got {d.child._zdc_resolved_reset_domain!r}"
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Tests: multiple children with mixed overrides
# ---------------------------------------------------------------------------

class TestMixedOverrides:
    """Some children overridden, some not — correct propagation for each."""

    def test_three_children_two_domains(self):
        """Three children: a=default, b=fast, c=fast. Each increments correctly."""
        async def _run():
            async with zdc.simulate(P5ThreeChildTop) as d:
                # Verify elaboration overrides
                assert d.b._zdc_resolved_clock_domain is d.fast_clk, "b should be on fast_clk"
                assert d.c._zdc_resolved_clock_domain is d.fast_clk, "c should be on fast_clk"
                assert d.a.__dict__.get('_zdc_resolved_clock_domain') is not d.fast_clk, \
                    "a should not be on fast_clk"

                # 1 default tick
                await d.domain.tick(1)
                # 3 fast ticks
                await d.fast_clk_sim.tick(3)
                return d.a.count, d.b.count, d.c.count

        a, b, c = asyncio.run(_run())
        assert a == 1, f"a (default domain) expected 1, got {a}"
        assert b == 3, f"b (fast domain) expected 3, got {b}"
        assert c == 3, f"c (fast domain) expected 3, got {c}"
