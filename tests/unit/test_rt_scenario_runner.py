"""Tests for ScenarioRunner, run_action, run_action_sync (Phase 1)."""
from __future__ import annotations

import asyncio
import dataclasses as dc

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.scenario_runner import (
    ScenarioRunner,
    run_action,
    run_action_sync,
)


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@zdc.dataclass
class SimpleCpu(zdc.Component):
    pass


@zdc.dataclass
class SimpleAction(zdc.Action[SimpleCpu]):
    x: int = zdc.rand(domain=(1, 63))
    _bodies: list = dc.field(default_factory=list, compare=False)

    async def body(self): self._bodies.append(self.x)


@zdc.dataclass
class ErrorAction(zdc.Action[SimpleCpu]):
    async def body(self): raise ValueError("intentional error")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_awaits_action_body():
    cpu = SimpleCpu()
    runner = ScenarioRunner(cpu, seed=42)
    action = _run(runner.run(SimpleAction))
    assert len(action._bodies) == 1


def test_same_seed_same_result():
    cpu = SimpleCpu()
    a = _run(ScenarioRunner(cpu, seed=42).run(SimpleAction))
    b = _run(ScenarioRunner(cpu, seed=42).run(SimpleAction))
    assert a.x == b.x


def test_different_seed_different_result():
    cpu = SimpleCpu()
    results = set()
    for seed in range(20):
        action = _run(ScenarioRunner(cpu, seed=seed).run(SimpleAction))
        results.add(action.x)
    # With 20 different seeds across range 1–63, we expect at least 2 distinct values
    assert len(results) > 1


def test_run_n_sequential():
    cpu = SimpleCpu()
    runner = ScenarioRunner(cpu, seed=0)
    bodies = []

    @zdc.dataclass
    class Counter(zdc.Action[SimpleCpu]):
        async def body(self): bodies.append(1)

    _run(runner.run_n(Counter, 3))
    assert sum(bodies) == 3


def test_seed_advances_between_runs():
    cpu = SimpleCpu()
    runner = ScenarioRunner(cpu, seed=0)
    a = _run(runner.run(SimpleAction))
    b = _run(runner.run(SimpleAction))
    # Across two runs the seed is advanced; results may differ
    # (not guaranteed to differ but seed must have changed — check state)
    assert runner._seed != 0


def test_run_action_helper():
    cpu = SimpleCpu()
    action = _run(run_action(cpu, SimpleAction, seed=42))
    assert isinstance(action, SimpleAction)
    assert len(action._bodies) == 1


def test_run_action_sync_helper():
    cpu = SimpleCpu()
    action = run_action_sync(cpu, SimpleAction, seed=42)
    assert isinstance(action, SimpleAction)


def test_run_action_sync_raises_on_error():
    cpu = SimpleCpu()
    with pytest.raises(ValueError, match="intentional error"):
        run_action_sync(cpu, ErrorAction)


def test_run_returns_action_instance():
    cpu = SimpleCpu()
    runner = ScenarioRunner(cpu, seed=0)
    result = _run(runner.run(SimpleAction))
    assert isinstance(result, SimpleAction)


def test_random_seed_when_none():
    cpu = SimpleCpu()
    runner = ScenarioRunner(cpu, seed=None)
    action = _run(runner.run(SimpleAction))
    assert action is not None
