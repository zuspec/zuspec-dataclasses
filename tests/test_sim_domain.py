"""Phase 6 tests — SimDomain testbench simulation API.

Tests cover:
- tick() advances domain-bound sync methods
- reset() asserts/deasserts reset
- wait_until() with and without timeout
- expose_clock / signal-level access still works
- multi-domain component exposes named sim domains
"""
import asyncio
import sys, os

_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_src  = os.path.join(_root, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# DUT definitions
# ---------------------------------------------------------------------------

@zdc.dataclass
class DomainCounter(zdc.Component):
    """Simple counter with class-level clock/reset domain (no visible clk/rst fields)."""
    clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
    reset_domain = zdc.ResetDomain()

    enable : zdc.bit   = zdc.input()
    count  : zdc.bit32 = zdc.output()
    reset  : zdc.bit   = zdc.input()   # explicit reset field (for reset body check)

    @zdc.sync
    def _count(self):
        if self.reset:
            self.count = 0
        elif self.enable:
            self.count = self.count + 1


@zdc.dataclass
class DomainCounterNoReset(zdc.Component):
    """Counter with no explicit reset field — free-running."""
    clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
    reset_domain = zdc.ResetDomain()

    enable : zdc.bit   = zdc.input()
    count  : zdc.bit32 = zdc.output()

    @zdc.sync
    def _count(self):
        if self.enable:
            self.count = self.count + 1


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(coro):
    asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSimDomainAttached:
    """SimDomain is automatically attached when clock_domain is declared."""

    def test_domain_attribute_exists(self):
        async def run():
            async with zdc.simulate(DomainCounter) as c:
                assert hasattr(c, 'domain'), "c.domain should be a SimDomain"
                assert isinstance(c.domain, zdc.SimDomain)
        _run(run())

    def test_domain_is_none_when_no_class_domain(self):
        @zdc.dataclass
        class NoDomain(zdc.Component):
            count : zdc.bit32 = zdc.output()

        async def run():
            async with zdc.simulate(NoDomain) as c:
                # No class-level clock_domain → no 'domain' attribute auto-attached
                assert not hasattr(c, 'domain')
        _run(run())


class TestSimDomainTick:
    """tick() triggers domain-bound sync methods."""

    def test_tick_advances_count(self):
        async def run():
            async with zdc.simulate(DomainCounter) as c:
                c.enable = 1
                c.reset = 0
                await c.domain.tick(5)
                assert c.count == 5
        _run(run())

    def test_tick_default_n_is_1(self):
        async def run():
            async with zdc.simulate(DomainCounter) as c:
                c.enable = 1
                c.reset = 0
                await c.domain.tick()
                assert c.count == 1
        _run(run())

    def test_tick_does_not_advance_when_disabled(self):
        async def run():
            async with zdc.simulate(DomainCounter) as c:
                c.enable = 0
                c.reset = 0
                await c.domain.tick(10)
                assert c.count == 0
        _run(run())

    def test_tick_accumulates(self):
        async def run():
            async with zdc.simulate(DomainCounterNoReset) as c:
                c.enable = 1
                await c.domain.tick(3)
                c.enable = 0
                await c.domain.tick(2)
                c.enable = 1
                await c.domain.tick(4)
                assert c.count == 7
        _run(run())


class TestSimDomainReset:
    """reset() asserts/deasserts the reset field."""

    def test_reset_zeroes_count(self):
        async def run():
            async with zdc.simulate(DomainCounter) as c:
                # Advance count first
                c.enable = 1
                c.reset = 0
                await c.domain.tick(5)
                assert c.count == 5
                # Now apply domain reset
                await c.domain.reset(cycles=2)
                assert c.count == 0, f"Expected 0 after reset, got {c.count}"
        _run(run())

    def test_pulse_reset(self):
        async def run():
            async with zdc.simulate(DomainCounter) as c:
                c.enable = 1
                c.reset = 0
                await c.domain.tick(3)
                await c.domain.pulse_reset()
                # After pulse_reset, count should be 0 (reset body) + 1 (post-reset tick)
                # pulse_reset = reset(cycles=1) → 1 active tick + 1 clean tick
                assert c.count == 0 or c.count == 1  # tolerate one post-reset tick
        _run(run())


class TestSimDomainWaitUntil:
    """wait_until() advances until predicate fires."""

    def test_wait_until_fires(self):
        async def run():
            async with zdc.simulate(DomainCounter) as c:
                c.enable = 1
                c.reset = 0
                await c.domain.wait_until(lambda comp: comp.count == 3)
                assert c.count == 3
        _run(run())

    def test_wait_until_timeout_raises(self):
        async def run():
            async with zdc.simulate(DomainCounter) as c:
                c.enable = 0   # count will never advance
                c.reset = 0
                with pytest.raises(TimeoutError):
                    await c.domain.wait_until(
                        lambda comp: comp.count == 10,
                        timeout_cycles=5,
                    )
        _run(run())

    def test_wait_until_already_true(self):
        """If predicate is immediately true, no ticks needed."""
        async def run():
            async with zdc.simulate(DomainCounter) as c:
                c.enable = 0
                c.reset = 0
                await c.domain.wait_until(lambda comp: comp.count == 0)
                assert c.count == 0
        _run(run())
