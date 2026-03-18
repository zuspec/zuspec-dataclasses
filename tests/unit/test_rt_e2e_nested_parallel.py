"""End-to-end tests: two-level parallel blocks with shared resource pools."""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import ClaimPool
from zuspec.dataclasses.rt.resource_rt import make_resource
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Hardware model
# ---------------------------------------------------------------------------

@zdc.dataclass
class Bus(zdc.Resource):
    id: int = 0


def _four_buses():
    buses = []
    for i in range(4):
        b = make_resource(Bus)
        b.id = i
        buses.append(b)
    return ClaimPool.fromList(buses)


@zdc.dataclass
class SoC(zdc.Component):
    buses: ClaimPool = zdc.pool(default_factory=_four_buses)


# ---------------------------------------------------------------------------
# Leaf actions — each claims one bus
# ---------------------------------------------------------------------------

@zdc.dataclass
class Leaf(zdc.Action[SoC]):
    bus: Bus = zdc.lock()
    _executed: bool = False

    async def body(self):
        self._executed = True


# ---------------------------------------------------------------------------
# Middle-level compounds: two leaves in parallel
# ---------------------------------------------------------------------------

@zdc.dataclass
class Middle(zdc.Action[SoC]):
    a: Leaf = None
    b: Leaf = None

    async def activity(self):
        with zdc.parallel():
            await self.a()
            await self.b()


# ---------------------------------------------------------------------------
# Top compound: two Middle actions in parallel  → 4 total leaf claims
# ---------------------------------------------------------------------------

@zdc.dataclass
class Top(zdc.Action[SoC]):
    m0: Middle = None
    m1: Middle = None

    async def activity(self):
        with zdc.parallel():
            await self.m0()
            await self.m1()


# ---------------------------------------------------------------------------
# Three-leaf sequential compound (for the schedule test)
# ---------------------------------------------------------------------------

@zdc.dataclass
class SeqLeafA(zdc.Action[SoC]):
    bus: Bus = zdc.lock()
    async def body(self): pass


@zdc.dataclass
class SeqLeafB(zdc.Action[SoC]):
    bus: Bus = zdc.lock()
    async def body(self): pass


@zdc.dataclass
class SeqCompound(zdc.Action[SoC]):
    a: SeqLeafA = None
    b: SeqLeafB = None

    async def activity(self):
        await self.a()
        await self.b()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_two_level_parallel_all_leaves_run():
    """Top→parallel(Middle, Middle)→parallel(Leaf,Leaf): all 4 leaves run."""
    comp = SoC()
    result = _run(ScenarioRunner(comp, seed=1).run(Top))
    assert result.m0 is not None
    assert result.m1 is not None
    assert result.m0.a is not None and result.m0.a._executed
    assert result.m0.b is not None and result.m0.b._executed
    assert result.m1.a is not None and result.m1.a._executed
    assert result.m1.b is not None and result.m1.b._executed


def test_two_level_parallel_buses_all_different():
    """Within each Middle parallel, the two Leaf actions claim distinct buses."""
    comp = SoC()
    result = _run(ScenarioRunner(comp, seed=2).run(Top))
    # Within m0: a and b must hold different bus instances simultaneously
    assert result.m0.a.bus is not result.m0.b.bus, "m0.a and m0.b share a bus"
    # Within m1: a and b must hold different bus instances simultaneously
    assert result.m1.a.bus is not result.m1.b.bus, "m1.a and m1.b share a bus"


def test_two_level_parallel_buses_released():
    """After top-level parallel completes, all 4 buses are free."""
    comp = SoC()
    _run(ScenarioRunner(comp, seed=3).run(Top))
    assert all(s == 0 for s in comp.buses._state)


def test_two_level_parallel_run_n_no_leak():
    """run_n(5) with nested parallel never leaks bus resources."""
    comp = SoC()
    _run(ScenarioRunner(comp, seed=4).run_n(Top, 5))
    assert all(s == 0 for s in comp.buses._state)


def test_sequential_compound_both_leaves_run():
    """Sequential compound: both leaf bodies execute."""
    comp = SoC()
    result = _run(ScenarioRunner(comp, seed=5).run(SeqCompound))
    assert result.a is not None
    assert result.b is not None


def test_sequential_compound_buses_released():
    """After sequential compound, buses are released."""
    comp = SoC()
    _run(ScenarioRunner(comp, seed=6).run(SeqCompound))
    assert all(s == 0 for s in comp.buses._state)
