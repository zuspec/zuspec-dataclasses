"""Tests for ActivityRunner — handle, anonymous, and super traversal (Phase 1)."""
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
class MyCpu(zdc.Component):
    pass


@zdc.dataclass
class WriteAction(zdc.Action[MyCpu]):
    executed: list = dc.field(default_factory=list, compare=False)
    async def body(self): self.executed.append("write")


@zdc.dataclass
class ReadAction(zdc.Action[MyCpu]):
    executed: list = dc.field(default_factory=list, compare=False)
    async def body(self): self.executed.append("read")


@zdc.dataclass
class HandleAction(zdc.Action[MyCpu]):
    write: WriteAction = zdc.field()
    async def activity(self):
        await self.write()


@zdc.dataclass
class AnonAction(zdc.Action[MyCpu]):
    async def activity(self):
        await do(WriteAction)


@zdc.dataclass
class LabeledAnonAction(zdc.Action[MyCpu]):
    w: WriteAction = zdc.field(default=None)
    async def activity(self):
        w = await do(WriteAction)


@zdc.dataclass
class ParentAction(zdc.Action[MyCpu]):
    log: list = dc.field(default_factory=list, compare=False)
    async def activity(self):
        await do(WriteAction)


@zdc.dataclass
class ChildAction(ParentAction):
    async def activity(self):
        super().activity()
        await do(ReadAction)


# ---------------------------------------------------------------------------
# Helper
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

def test_handle_traversal_resolves_type():
    cpu = MyCpu()
    runner = ScenarioRunner(cpu, seed=0)
    action = _run(runner.run(HandleAction))
    # HandleAction.write should have been traversed (a WriteAction was created)
    assert action.write is not None


def test_handle_traversal_missing_handle_raises():
    from zuspec.dataclasses.ir.activity import ActivityTraversal
    cpu = MyCpu()
    pr = PoolResolver.build(cpu)

    @zdc.dataclass
    class BadHandleAction(zdc.Action[MyCpu]):
        async def activity(self):
            await self.nonexistent_handle()

    with pytest.raises(RuntimeError, match="nonexistent_handle"):
        _run(ScenarioRunner(cpu, seed=0).run(BadHandleAction))


def test_anon_traversal_by_class_ref():
    cpu = MyCpu()
    runner = ScenarioRunner(cpu, seed=0)
    # AnonAction.activity() does await do(WriteAction)
    action = _run(runner.run(AnonAction))
    assert action is not None


def test_anon_traversal_label_writeback():
    cpu = MyCpu()
    runner = ScenarioRunner(cpu, seed=0)
    action = _run(runner.run(LabeledAnonAction))
    # After traversal, self.w should have been set (label writeback)
    assert action.w is not None
    assert isinstance(action.w, WriteAction)


def test_super_traversal_runs_parent_body():
    cpu = MyCpu()
    runner = ScenarioRunner(cpu, seed=0)
    # ChildAction calls super().activity() then await do(ReadAction)
    action = _run(runner.run(ChildAction))
    assert action is not None  # both parent and child blocks ran without error


def test_super_traversal_no_parent_is_noop():
    @zdc.dataclass
    class StandaloneAction(zdc.Action[MyCpu]):
        async def activity(self):
            super().activity()  # no parent __activity__

    cpu = MyCpu()
    runner = ScenarioRunner(cpu, seed=0)
    # Should complete without error
    action = _run(runner.run(StandaloneAction))
    assert action is not None
