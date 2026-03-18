"""Tests for rt/binding_solver.py — Phase 2."""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import ClaimPool
from zuspec.dataclasses.rt.resource_rt import make_resource
from zuspec.dataclasses.rt.pool_resolver import PoolResolver
from zuspec.dataclasses.rt.action_context import ActionContext
from zuspec.dataclasses.rt.binding_solver import BindingSolver, HeadAssignment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@zdc.dataclass
class DmaChannel(zdc.Resource):
    pass


def _pool(n=3):
    return ClaimPool.fromList([make_resource(DmaChannel) for _ in range(n)])


@zdc.dataclass
class DmaComp(zdc.Component):
    channels: ClaimPool = zdc.pool(default_factory=lambda: _pool(3))


@zdc.dataclass
class WriteAction(zdc.Action[DmaComp]):
    chan: DmaChannel = zdc.lock()
    async def body(self):
        pass


@zdc.dataclass
class ReadAction(zdc.Action[DmaComp]):
    chan: DmaChannel = zdc.lock()
    async def body(self):
        pass


def _make_ctx(comp):
    pr = PoolResolver.build(comp)
    return ActionContext(action=None, comp=comp, pool_resolver=pr, seed=42)


# ---------------------------------------------------------------------------
# solve_heads() tests
# ---------------------------------------------------------------------------

def test_solve_heads_returns_one_per_branch():
    """solve_heads returns one HeadAssignment per head action type."""
    comp = DmaComp()
    ctx = _make_ctx(comp)
    solver = BindingSolver()
    result = solver.solve_heads([WriteAction, ReadAction], ctx)
    assert len(result) == 2
    assert all(isinstance(r, HeadAssignment) for r in result)
    assert result[0].branch_index == 0
    assert result[1].branch_index == 1


def test_solve_heads_all_different():
    """Two branches get different instance_ids from the same pool."""
    comp = DmaComp()
    ctx = _make_ctx(comp)
    solver = BindingSolver()
    result = solver.solve_heads([WriteAction, ReadAction], ctx)
    id0 = result[0].resource_hints.get("chan")
    id1 = result[1].resource_hints.get("chan")
    assert id0 is not None
    assert id1 is not None
    assert id0 != id1


def test_solve_heads_empty_input():
    """Empty head list returns empty list."""
    comp = DmaComp()
    ctx = _make_ctx(comp)
    result = BindingSolver().solve_heads([], ctx)
    assert result == []


def test_solve_heads_single_branch():
    """Single branch gets a valid instance_id."""
    comp = DmaComp()
    ctx = _make_ctx(comp)
    result = BindingSolver().solve_heads([WriteAction], ctx)
    assert len(result) == 1
    hint = result[0].resource_hints.get("chan")
    assert hint is not None
    assert 0 <= hint < 3  # pool has 3 resources


def test_solve_heads_infeasible_raises():
    """More branches than pool instances raises RuntimeError."""
    @zdc.dataclass
    class TinyComp(zdc.Component):
        channels: ClaimPool = zdc.pool(
            default_factory=lambda: ClaimPool.fromList([make_resource(DmaChannel)])
        )

    @zdc.dataclass
    class ActionA(zdc.Action[TinyComp]):
        chan: DmaChannel = zdc.lock()
        async def body(self): pass

    @zdc.dataclass
    class ActionB(zdc.Action[TinyComp]):
        chan: DmaChannel = zdc.lock()
        async def body(self): pass

    comp = TinyComp()
    ctx2 = ActionContext(action=None, comp=comp, pool_resolver=PoolResolver.build(comp), seed=0)

    with pytest.raises(RuntimeError, match="infeasible"):
        BindingSolver().solve_heads([ActionA, ActionB], ctx2)


def test_solve_heads_no_lock_fields():
    """Actions without lock fields get empty resource_hints."""
    @zdc.dataclass
    class NoLockAction(zdc.Action[DmaComp]):
        async def body(self): pass

    comp = DmaComp()
    ctx = _make_ctx(comp)
    result = BindingSolver().solve_heads([NoLockAction, NoLockAction], ctx)
    assert len(result) == 2
    assert result[0].resource_hints == {}
    assert result[1].resource_hints == {}


def test_solve_heads_deterministic_with_seed():
    """Same seed produces same assignment."""
    comp = DmaComp()
    pr = PoolResolver.build(comp)
    ctx = ActionContext(action=None, comp=comp, pool_resolver=pr, seed=99)
    r1 = BindingSolver().solve_heads([WriteAction, ReadAction], ctx)
    r2 = BindingSolver().solve_heads([WriteAction, ReadAction], ctx)
    assert r1[0].resource_hints == r2[0].resource_hints
    assert r1[1].resource_hints == r2[1].resource_hints
