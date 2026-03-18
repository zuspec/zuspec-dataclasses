"""Tests for parallel/schedule/atomic execution in ActivityRunner — Phase 2."""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import ClaimPool
from zuspec.dataclasses.rt.resource_rt import make_resource
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Component / resource fixtures (module-level so activity parser can resolve)
# ---------------------------------------------------------------------------

@zdc.dataclass
class DmaChannel(zdc.Resource):
    pass


def _pool(n=2):
    return ClaimPool.fromList([make_resource(DmaChannel) for _ in range(n)])


@zdc.dataclass
class DmaComp(zdc.Component):
    channels: ClaimPool = zdc.pool(default_factory=_pool)


# ---------------------------------------------------------------------------
# Leaf actions (module-level so _resolve_action_type can find them)
# ---------------------------------------------------------------------------

_parallel_executed = []

@zdc.dataclass
class ParBranchA(zdc.Action[DmaComp]):
    async def body(self):
        _parallel_executed.append("A")


@zdc.dataclass
class ParBranchB(zdc.Action[DmaComp]):
    async def body(self):
        _parallel_executed.append("B")


@zdc.dataclass
class LockAction(zdc.Action[DmaComp]):
    chan: DmaChannel = zdc.lock()
    async def body(self):
        pass


_count = [0]

@zdc.dataclass
class CountLeaf(zdc.Action[DmaComp]):
    async def body(self):
        _count[0] += 1


@zdc.dataclass
class SchedTaskA(zdc.Action[DmaComp]):
    async def body(self):
        _parallel_executed.append("SA")


@zdc.dataclass
class SchedTaskB(zdc.Action[DmaComp]):
    async def body(self):
        _parallel_executed.append("SB")


# ---------------------------------------------------------------------------
# Parallel block tests
# ---------------------------------------------------------------------------

@zdc.dataclass
class ParAction(zdc.Action[DmaComp]):
    async def activity(self):
        with zdc.parallel():
            do(ParBranchA)
            do(ParBranchB)


def test_parallel_both_branches_execute():
    """Both branches of a parallel block are executed."""
    _parallel_executed.clear()
    comp = DmaComp()
    _run(ScenarioRunner(comp, seed=0).run(ParAction))
    assert "A" in _parallel_executed
    assert "B" in _parallel_executed


@zdc.dataclass
class ParLockAction(zdc.Action[DmaComp]):
    async def activity(self):
        with zdc.parallel():
            do(LockAction)
            do(LockAction)


def test_parallel_resource_contention_resolved():
    """Two parallel branches with lock fields get distinct resource instances."""
    comp = DmaComp()
    # Should not deadlock — 2 branches, 2 channels
    _run(ScenarioRunner(comp, seed=0).run(ParLockAction))


@zdc.dataclass
class Par3Action(zdc.Action[DmaComp]):
    async def activity(self):
        with zdc.parallel():
            do(CountLeaf)
            do(CountLeaf)
            do(CountLeaf)


def test_parallel_three_branches():
    """Three parallel branches all execute."""
    _count[0] = 0
    comp = DmaComp()
    _run(ScenarioRunner(comp, seed=0).run(Par3Action))
    assert _count[0] == 3


# ---------------------------------------------------------------------------
# Schedule block tests
# ---------------------------------------------------------------------------

@zdc.dataclass
class SchedAction(zdc.Action[DmaComp]):
    async def activity(self):
        with zdc.schedule():
            do(SchedTaskA)
            do(SchedTaskB)


def test_schedule_all_branches_execute():
    """All schedule branches execute (Phase 2: treated as parallel)."""
    _parallel_executed.clear()
    comp = DmaComp()
    _run(ScenarioRunner(comp, seed=0).run(SchedAction))
    assert "SA" in _parallel_executed
    assert "SB" in _parallel_executed


# ---------------------------------------------------------------------------
# Atomic block tests
# ---------------------------------------------------------------------------

_atom_count = [0]


@zdc.dataclass
class AtomicLeaf(zdc.Action[DmaComp]):
    async def body(self):
        _atom_count[0] += 1


@zdc.dataclass
class AtomAction(zdc.Action[DmaComp]):
    async def activity(self):
        with zdc.atomic():
            do(AtomicLeaf)
            do(AtomicLeaf)


def test_atomic_block_executes():
    """Atomic block executes all its statements."""
    _atom_count[0] = 0
    comp = DmaComp()
    _run(ScenarioRunner(comp, seed=0).run(AtomAction))
    assert _atom_count[0] == 2


# ---------------------------------------------------------------------------
# Resource lock/release across sequential actions
# ---------------------------------------------------------------------------

_seq_count = [0]


@zdc.dataclass
class SeqUseChannel(zdc.Action[DmaComp]):
    chan: DmaChannel = zdc.lock()
    async def body(self):
        _seq_count[0] += 1


@zdc.dataclass
class SeqAction(zdc.Action[DmaComp]):
    async def activity(self):
        do(SeqUseChannel)
        do(SeqUseChannel)


def test_sequential_resource_reuse():
    """Second sequential action can acquire the same resource released by first."""
    _seq_count[0] = 0
    comp = DmaComp()
    _run(ScenarioRunner(comp, seed=0).run(SeqAction))
    assert _seq_count[0] == 2
