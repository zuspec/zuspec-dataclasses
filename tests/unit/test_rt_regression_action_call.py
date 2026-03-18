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
