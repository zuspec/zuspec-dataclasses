"""Regression tests — Action.__call__ backwards compatibility (Phase 1)."""
from __future__ import annotations

import asyncio
import dataclasses as dc

import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@zdc.dataclass
class MyCpu(zdc.Component):
    pass


@zdc.dataclass
class TopCpu(zdc.Component):
    cpu1: MyCpu = zdc.inst()
    cpu2: MyCpu = zdc.inst()


@zdc.dataclass
class MyAction(zdc.Action[MyCpu]):
    x: int = zdc.rand(domain=(1, 63))
    _body_called: bool = dc.field(default=False, compare=False)

    async def body(self):
        self._body_called = True


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_action_call_runs_body():
    cpu = MyCpu()
    action = MyAction()
    result = _run(action(cpu))
    assert result._body_called is True


def test_action_call_sets_comp():
    cpu = MyCpu()
    action = MyAction()
    _run(action(cpu))
    assert action.comp is cpu


def test_action_call_solves_fields():
    cpu = MyCpu()
    action = MyAction()
    _run(action(cpu))
    assert 1 <= action.x <= 63


def test_action_call_returns_self():
    cpu = MyCpu()
    action = MyAction()
    result = _run(action(cpu))
    assert result is action


def test_action_call_nested_component():
    """Verifies that Action.__call__ works when context has nested components."""
    top = TopCpu()
    action = MyAction()
    _run(action(top))
    # comp should be one of the nested MyCpu instances
    assert action.comp in (top.cpu1, top.cpu2)


# ---------------------------------------------------------------------------
# Caching tests (Phase 1 — ActionInfra)
# ---------------------------------------------------------------------------

def test_action_call_caches_infra_on_component():
    """After first call, _impl._action_infra should be populated."""
    cpu = MyCpu()
    assert cpu._impl._action_infra is None
    action = MyAction()
    _run(action(cpu))
    assert cpu._impl._action_infra is not None


def test_action_call_reuses_cached_infra():
    """Second call should reuse the exact same ActionInfra instance."""
    cpu = MyCpu()
    _run(MyAction()(cpu))
    infra_first = cpu._impl._action_infra
    _run(MyAction()(cpu))
    infra_second = cpu._impl._action_infra
    assert infra_first is infra_second


def test_action_call_infra_isolated_per_component():
    """Each component gets its own ActionInfra cache, not shared."""
    cpu_a = MyCpu()
    cpu_b = MyCpu()
    _run(MyAction()(cpu_a))
    _run(MyAction()(cpu_b))
    assert cpu_a._impl._action_infra is not cpu_b._impl._action_infra


def test_action_call_fresh_seed_each_call():
    """Consecutive calls without a fixed seed should produce different seeds."""
    cpu = MyCpu()
    results = [_run(MyAction()(cpu)).x for _ in range(10)]
    # With a domain of (1, 63), 10 random picks should not all be identical
    assert len(set(results)) > 1

