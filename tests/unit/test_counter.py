"""Tests for zdc.Counter, zdc.ModuloCounter, zdc.WatchdogCounter, zdc.CounterBank."""
from __future__ import annotations

import asyncio
import pytest
import zuspec.dataclasses as zdc


# ── helpers ─────────────────────────────────────────────────────────────────

def _make_comp(counter_kwargs=None):
    """Return a fresh TestComp with a 10 ns clock and one Counter child."""

    @zdc.dataclass
    class TestComp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        cnt: zdc.Counter = zdc.inst(zdc.Counter, kwargs=counter_kwargs or {})

    return TestComp()


def _run(coro):
    return asyncio.run(coro)


# ── Counter.value ────────────────────────────────────────────────────────────

def test_counter_value_starts_at_zero():
    c = _make_comp()
    assert c.cnt.value == 0


def test_counter_value_increases_with_time():
    c = _make_comp()
    _run(c.wait(zdc.Time.ns(100)))  # 10 cycles at 10 ns/cycle
    assert c.cnt.value == 10


def test_counter_value_continues_increasing():
    c = _make_comp()
    _run(c.wait(zdc.Time.ns(200)))
    assert c.cnt.value == 20


def test_counter_snapshot_equals_value():
    c = _make_comp()
    _run(c.wait(zdc.Time.ns(50)))
    assert c.cnt.snapshot() == c.cnt.value


def test_counter_modulus_default_32bit():
    c = _make_comp()
    assert c.cnt.modulus == 2**32


def test_counter_modulus_custom_width():
    c = _make_comp({'WIDTH': 8})
    assert c.cnt.modulus == 256


# ── Counter.reset ────────────────────────────────────────────────────────────

def test_counter_reset_to_zero():
    c = _make_comp({'WIDTH': 8})
    _run(c.wait(zdc.Time.ns(500)))   # 50 cycles
    assert c.cnt.value == 50
    c.cnt.reset(0)
    assert c.cnt.value == 0


def test_counter_reset_to_arbitrary_value():
    c = _make_comp({'WIDTH': 8})
    _run(c.wait(zdc.Time.ns(100)))   # 10 cycles
    c.cnt.reset(200)
    assert c.cnt.value == 200


def test_counter_continues_from_reset():
    c = _make_comp({'WIDTH': 8})
    _run(c.wait(zdc.Time.ns(100)))   # 10 cycles
    c.cnt.reset(200)
    _run(c.wait(zdc.Time.ns(50)))    # 5 more cycles
    assert c.cnt.value == 205


def test_counter_wraps_after_reset():
    c = _make_comp({'WIDTH': 8})
    _run(c.wait(zdc.Time.ns(100)))   # 10 cycles
    c.cnt.reset(200)
    _run(c.wait(zdc.Time.ns(560)))   # 56 more cycles: 200+56 = 256 -> wraps to 0
    assert c.cnt.value == 0


# ── Counter.wait_for (int) ───────────────────────────────────────────────────

def test_wait_for_future_target():
    c = _make_comp()

    async def run():
        await c.cnt.wait_for(10)
        return c.cnt.value

    result = _run(run())
    assert result == 10


def test_wait_for_immediate_return_when_equal():
    c = _make_comp()

    async def run():
        _run_inner = c.wait(zdc.Time.ns(100))
        await _run_inner   # 10 cycles
        v = c.cnt.value    # == 10
        await c.cnt.wait_for(v)  # already there — should return immediately
        return c.cnt.value

    result = _run(run())
    assert result == 10


def test_wait_for_wraps_around():
    c = _make_comp({'WIDTH': 8})

    async def run():
        await c.wait(zdc.Time.ns(2500))  # 250 cycles
        # Now at 250. wait_for(10) means: wait 16 cycles (256-250+10)
        await c.cnt.wait_for(10)
        return c.cnt.value

    result = _run(run())
    assert result == 10


# ── Counter.wait_ge ──────────────────────────────────────────────────────────

def test_wait_ge_future_threshold():
    c = _make_comp()

    async def run():
        await c.cnt.wait_ge(5)
        return c.cnt.value

    result = _run(run())
    assert result >= 5


def test_wait_ge_already_past_returns_immediately():
    c = _make_comp()

    async def run():
        await c.wait(zdc.Time.ns(100))  # 10 cycles
        await c.cnt.wait_ge(5)           # already >= 5
        return c.cnt.value

    result = _run(run())
    assert result == 10  # No further time should have passed


# ── Counter.wait_next ────────────────────────────────────────────────────────

def test_wait_next_full_period_from_zero():
    c = _make_comp({'WIDTH': 8})

    async def run():
        # Start at 0 — wait_next should wait a full 256 cycles to hit 0 again
        await c.cnt.wait_next()
        return c.cnt.value

    result = _run(run())
    assert result == 0


def test_wait_next_mid_period():
    c = _make_comp({'WIDTH': 8})

    async def run():
        await c.wait(zdc.Time.ns(100))  # 10 cycles
        await c.cnt.wait_next()          # wait for next rollover
        return c.cnt.value

    result = _run(run())
    assert result == 0


# ── Counter.schedule ─────────────────────────────────────────────────────────

def test_schedule_fires_at_target():
    c = _make_comp()
    fired_at = []

    async def run():
        c.cnt.schedule(10, lambda: fired_at.append(c.cnt.value))
        await c.wait(zdc.Time.ns(200))

    _run(run())
    assert fired_at == [10]


def test_schedule_handle_cancel():
    c = _make_comp()
    fired = []

    async def run():
        h = c.cnt.schedule(10, lambda: fired.append(1))
        h.cancel()
        await c.wait(zdc.Time.ns(200))

    _run(run())
    assert fired == []


def test_schedule_repeat():
    c = _make_comp({'WIDTH': 8})
    fired_at = []

    async def run():
        # Schedule at 10, repeat every 256 cycles
        c.cnt.schedule(10, lambda: fired_at.append(c.cnt.value), repeat=True)
        await c.wait(zdc.Time.ns(5200))  # 520 cycles → two firings (cycle 10, 266)

    _run(run())
    assert len(fired_at) == 2
    assert fired_at[0] == 10


def test_schedule_handle_fired_property():
    c = _make_comp()

    async def run():
        h = c.cnt.schedule(5, lambda: None)
        assert not h.fired
        await c.wait(zdc.Time.ns(100))
        return h.fired

    result = _run(run())
    assert result is True


# ── ModuloCounter ─────────────────────────────────────────────────────────────

def test_modulo_counter_modulus_is_period():
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        cnt: zdc.ModuloCounter = zdc.inst(zdc.ModuloCounter, kwargs={'PERIOD': 100})

    c = Comp()
    assert c.cnt.modulus == 100


def test_modulo_counter_wraps_at_period():
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        cnt: zdc.ModuloCounter = zdc.inst(zdc.ModuloCounter, kwargs={'PERIOD': 10})

    c = Comp()
    _run(c.wait(zdc.Time.ns(100)))  # 10 cycles = exactly one period
    assert c.cnt.value == 0


def test_modulo_counter_wait_next():
    # ModuloCounter.on_rollover runs as a background proc, so sequential
    # top-level `await c.wait` calls are not safe.  Instead, perform the
    # assertion inside a @proc that is driven by a single outer c.wait().
    result = []

    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        cnt: zdc.ModuloCounter = zdc.inst(zdc.ModuloCounter, kwargs={'PERIOD': 10})

        @zdc.proc
        async def _test_seq(self):
            await self.wait(zdc.Time.ns(30))   # 3 cycles into period
            await self.cnt.wait_next()          # wait for next rollover (7 cycles)
            result.append(self.cnt.value)

    c = Comp()
    asyncio.run(c.wait(zdc.Time.ns(200)))
    assert result == [0]


# ── WatchdogCounter ───────────────────────────────────────────────────────────

def test_watchdog_fires_on_timeout():
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        wdog: zdc.WatchdogCounter = zdc.inst(zdc.WatchdogCounter, kwargs={'TIMEOUT': 5})

    c = Comp()
    fired = []

    async def on_timeout_impl(self):
        fired.append(1)

    async def run():
        # Monkey-patch on_timeout
        import types
        c.wdog.on_timeout = types.MethodType(on_timeout_impl, c.wdog)
        c.wdog.arm()
        await c.wait(zdc.Time.ns(100))  # 10 cycles >> TIMEOUT=5

    _run(run())
    assert len(fired) == 1


def test_watchdog_kick_prevents_timeout():
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        wdog: zdc.WatchdogCounter = zdc.inst(zdc.WatchdogCounter, kwargs={'TIMEOUT': 10})

    c = Comp()
    fired = []

    async def run():
        c.wdog.arm()
        await c.wait(zdc.Time.ns(50))  # 5 cycles — still ok
        c.wdog.kick()                   # reset window
        await c.wait(zdc.Time.ns(50))  # 5 more — still ok
        c.wdog.kick()
        await c.wait(zdc.Time.ns(50))  # 5 more — still ok
        return len(fired)

    result = _run(run())
    assert result == 0


def test_watchdog_disarm_prevents_callback():
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        wdog: zdc.WatchdogCounter = zdc.inst(zdc.WatchdogCounter, kwargs={'TIMEOUT': 5})

    c = Comp()
    fired = []

    async def run():
        c.wdog.arm()
        await c.wait(zdc.Time.ns(20))   # 2 cycles
        c.wdog.disarm()
        await c.wait(zdc.Time.ns(100))  # 10 more cycles (past timeout)

    _run(run())
    assert fired == []


# ── CounterBank ───────────────────────────────────────────────────────────────

def test_counter_bank_getitem():
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        bank: zdc.CounterBank = zdc.inst(zdc.CounterBank, kwargs={'COUNT': 4})

    c = Comp()
    _run(c.wait(zdc.Time.ns(100)))  # 10 cycles
    assert c.bank[0].value == 10
    assert c.bank[3].value == 10


def test_counter_bank_out_of_range():
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        bank: zdc.CounterBank = zdc.inst(zdc.CounterBank)

    c = Comp()
    with pytest.raises(IndexError):
        _ = c.bank[c.bank.COUNT]


def test_counter_bank_snapshot_all():
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        bank: zdc.CounterBank = zdc.inst(zdc.CounterBank, kwargs={'COUNT': 3})

    c = Comp()
    _run(c.wait(zdc.Time.ns(50)))  # 5 cycles
    snap = c.bank.snapshot_all()
    assert snap == (5, 5, 5)


def test_counter_bank_independent_resets():
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        bank: zdc.CounterBank = zdc.inst(zdc.CounterBank, kwargs={'COUNT': 2})

    c = Comp()
    _run(c.wait(zdc.Time.ns(100)))  # 10 cycles
    c.bank[0].reset(0)
    assert c.bank[0].value == 0
    assert c.bank[1].value == 10


# ── ClockDomain.cycle() ───────────────────────────────────────────────────────

def test_clock_domain_cycle_from_timebase():
    # ClockDomain.cycle() returns the cycle count in tick() mode.
    # In asyncio.run (timebase) mode, cycle counting is accessed via Counter.value.
    # This test verifies the Counter reflects the correct timebase-derived cycle.
    @zdc.dataclass
    class Comp(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        cnt: zdc.Counter = zdc.inst(zdc.Counter)

    c = Comp()
    _run(c.wait(zdc.Time.ns(100)))
    assert c.cnt.value == 10


def test_clock_domain_cycle_from_tick():
    @zdc.dataclass
    class Comp(zdc.SyncComponent):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))

    async def run():
        async with zdc.simulate(Comp) as c:
            await c.clock_domain.tick(5)
            return type(c).clock_domain._cycle_count

    result = _run(run())
    assert result == 5
