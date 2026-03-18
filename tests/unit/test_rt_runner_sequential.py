"""Tests for ActivityRunner — sequential traversal lifecycle (Phase 1)."""
from __future__ import annotations

import asyncio
import dataclasses as dc
from unittest import mock

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.activity_runner import ActivityRunner
from zuspec.dataclasses.rt.action_context import ActionContext
from zuspec.dataclasses.rt.pool_resolver import PoolResolver
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@zdc.dataclass
class SimpleCpu(zdc.Component):
    pass


@zdc.dataclass
class DmaCpu(zdc.Component):
    pass


@zdc.dataclass
class SimpleAction(zdc.Action[SimpleCpu]):
    x: int = zdc.rand(domain=(1, 63))
    _call_log: list = dc.field(default_factory=list, compare=False)

    async def body(self) -> None:
        self._call_log.append(("body", self.x))


@zdc.dataclass
class TrackingAction(zdc.Action[SimpleCpu]):
    events: list = dc.field(default_factory=list, compare=False)

    def pre_solve(self)  -> None: self.events.append("pre_solve")
    def post_solve(self) -> None: self.events.append("post_solve")
    async def body(self) -> None: self.events.append("body")


@zdc.dataclass
class CompoundAction(zdc.Action[SimpleCpu]):
    events: list = dc.field(default_factory=list, compare=False)

    async def activity(self):
        do(SimpleAction)
        do(SimpleAction)


@zdc.dataclass
class NeedsDmaCpu(zdc.Action[DmaCpu]):
    async def body(self): pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def _runner_ctx(comp):
    pr = PoolResolver.build(comp)
    ctx = ActionContext(action=None, comp=comp, pool_resolver=pr, seed=0)
    return ActivityRunner(), ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_atomic_body_called():
    cpu = SimpleCpu()
    runner, ctx = _runner_ctx(cpu)
    action = _run(runner._traverse(SimpleAction, [], ctx))
    assert any(e[0] == "body" for e in action._call_log)


def test_rand_fields_not_default_after_run():
    cpu = SimpleCpu()
    runner, ctx = _runner_ctx(cpu)
    action = _run(runner._traverse(SimpleAction, [], ctx))
    assert action.x != 0  # should have been randomized to 1–63


def test_pre_solve_before_randomize():
    cpu = SimpleCpu()
    runner, ctx = _runner_ctx(cpu)
    action = _run(runner._traverse(TrackingAction, [], ctx))
    pre_idx = action.events.index("pre_solve")
    post_idx = action.events.index("post_solve")
    assert pre_idx < post_idx


def test_post_solve_after_randomize():
    cpu = SimpleCpu()
    runner, ctx = _runner_ctx(cpu)
    action = _run(runner._traverse(TrackingAction, [], ctx))
    assert action.events.index("post_solve") > action.events.index("pre_solve")


def test_body_after_post_solve():
    cpu = SimpleCpu()
    runner, ctx = _runner_ctx(cpu)
    action = _run(runner._traverse(TrackingAction, [], ctx))
    assert action.events.index("body") > action.events.index("post_solve")


def test_lifecycle_ordering():
    cpu = SimpleCpu()
    runner, ctx = _runner_ctx(cpu)
    action = _run(runner._traverse(TrackingAction, [], ctx))
    assert action.events == ["pre_solve", "post_solve", "body"]


def test_comp_assigned():
    cpu = SimpleCpu()
    runner, ctx = _runner_ctx(cpu)
    action = _run(runner._traverse(SimpleAction, [], ctx))
    assert action.comp is cpu


def test_run_n_calls_body_n_times():
    cpu = SimpleCpu()
    runner = ScenarioRunner(cpu, seed=0)
    bodies = []

    @zdc.dataclass
    class Counter(zdc.Action[SimpleCpu]):
        async def body(self): bodies.append(1)

    _run(runner.run_n(Counter, 5))
    assert sum(bodies) == 5


def test_no_comp_raises_runtime_error():
    cpu = SimpleCpu()
    runner, ctx = _runner_ctx(cpu)
    with pytest.raises(RuntimeError):
        _run(runner._traverse(NeedsDmaCpu, [], ctx))


def test_error_message_contains_action_type():
    cpu = SimpleCpu()
    runner, ctx = _runner_ctx(cpu)
    with pytest.raises(RuntimeError, match="DmaCpu"):
        _run(runner._traverse(NeedsDmaCpu, [], ctx))
