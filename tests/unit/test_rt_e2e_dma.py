"""End-to-end DMA transfer scenario — PSS LRM Example 45 pattern.

Tests the full runtime integration: compound action, parallel block,
resource locking, ClaimPool, rand fields, seed reproducibility.
"""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import ClaimPool
from zuspec.dataclasses.rt.resource_rt import make_resource
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner
from zuspec.dataclasses.activity_dsl import do


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Domain model — module-level so the activity parser can resolve types
# ---------------------------------------------------------------------------

@zdc.dataclass
class DmaChannel(zdc.Resource):
    """Exclusive DMA hardware channel."""
    id: int = 0


def _two_channels():
    ch0 = make_resource(DmaChannel)
    ch0.id = 0
    ch1 = make_resource(DmaChannel)
    ch1.id = 1
    return ClaimPool.fromList([ch0, ch1])


@zdc.dataclass
class DmaEngine(zdc.Component):
    """DMA subsystem component owning the channel pool."""
    channels: ClaimPool = zdc.pool(default_factory=_two_channels)


@zdc.dataclass
class DmaRead(zdc.Action[DmaEngine]):
    """Reads from memory; claims one DMA channel exclusively."""
    chan: DmaChannel = zdc.lock()
    addr: zdc.u32 = zdc.rand()
    size: zdc.u8 = zdc.rand()
    _body_called: bool = False

    async def body(self):
        self._body_called = True


@zdc.dataclass
class DmaWrite(zdc.Action[DmaEngine]):
    """Writes to memory; claims one DMA channel exclusively."""
    chan: DmaChannel = zdc.lock()
    addr: zdc.u32 = zdc.rand()
    size: zdc.u8 = zdc.rand()
    _body_called: bool = False

    async def body(self):
        self._body_called = True


@zdc.dataclass
class DmaTransfer(zdc.Action[DmaEngine]):
    """Compound action: parallel read + write."""
    rd: DmaRead = None
    wr: DmaWrite = None

    async def activity(self):
        with zdc.parallel():
            await self.rd()
            await self.wr()


# ---------------------------------------------------------------------------
# Component with two DmaEngine children (for hierarchy test)
# ---------------------------------------------------------------------------

@zdc.dataclass
class DmaTop(zdc.Component):
    eng0: DmaEngine = zdc.field(default_factory=DmaEngine)
    eng1: DmaEngine = zdc.field(default_factory=DmaEngine)


# Action bound to DmaTop that needs DmaEngine — resolved hierarchically
@zdc.dataclass
class DmaReadTop(zdc.Action[DmaTop]):
    chan: DmaChannel = zdc.lock()
    addr: zdc.u32 = zdc.rand()

    async def body(self):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_dma_sequential_transfer():
    """DmaTransfer compound action: both DmaRead and DmaWrite body() called."""
    comp = DmaEngine()
    result = _run(ScenarioRunner(comp, seed=42).run(DmaTransfer))
    assert result.rd is not None
    assert result.wr is not None
    assert result.rd._body_called
    assert result.wr._body_called


def test_dma_rand_fields_solved():
    """addr and size fields are set (randomized, non-default None) after run."""
    comp = DmaEngine()
    result = _run(ScenarioRunner(comp, seed=42).run(DmaTransfer))
    assert result.rd.addr is not None
    assert result.rd.size is not None
    assert result.wr.addr is not None
    assert result.wr.size is not None


def test_dma_parallel_distinct_channels():
    """Parallel read/write each claim a distinct channel."""
    comp = DmaEngine()
    result = _run(ScenarioRunner(comp, seed=42).run(DmaTransfer))
    # Both held channels must differ (AllDifferent from BindingSolver)
    assert result.rd.chan is not result.wr.chan


def test_dma_channel_released_after_transfer():
    """After run, all channel claims are dropped — pool back to full size."""
    comp = DmaEngine()
    _run(ScenarioRunner(comp, seed=42).run(DmaTransfer))
    # Both channels must be unlocked (_state 0 = free)
    pool = comp.channels
    assert all(s == 0 for s in pool._state), f"Pool state still locked: {pool._state}"


def test_dma_run_n_no_channel_leak():
    """run_n(10) never deadlocks; pool always returns to full size."""
    comp = DmaEngine()
    runner = ScenarioRunner(comp, seed=99)
    _run(runner.run_n(DmaTransfer, 10))
    assert all(s == 0 for s in comp.channels._state)


def test_dma_seed_reproducible():
    """Same seed → same address/size in both read and write sub-actions."""
    comp1 = DmaEngine()
    r1 = _run(ScenarioRunner(comp1, seed=1234).run(DmaTransfer))

    comp2 = DmaEngine()
    r2 = _run(ScenarioRunner(comp2, seed=1234).run(DmaTransfer))

    assert r1.rd.addr == r2.rd.addr
    assert r1.rd.size == r2.rd.size
    assert r1.wr.addr == r2.wr.addr
    assert r1.wr.size == r2.wr.size


def test_dma_component_hierarchy():
    """DmaTop has two DmaEngine children; DmaRead can be run against DmaTop."""
    top = DmaTop()
    # DmaReadTop is bound to DmaTop — pool_resolver must find DmaChannel pools
    # in one of the child DmaEngine components
    result = _run(ScenarioRunner(top, seed=7).run(DmaReadTop))
    assert result.chan is not None
    assert result.addr is not None
