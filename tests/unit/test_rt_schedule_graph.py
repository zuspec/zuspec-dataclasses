"""Tests for ScheduleGraph topological sort."""
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.activity_runner import ScheduleGraph
from zuspec.dataclasses.rt.action_context import ActionContext
from unittest.mock import MagicMock

from zuspec.dataclasses.ir.activity import ActivityAnonTraversal


def _mock_ctx():
    ctx = MagicMock(spec=ActionContext)
    ctx.action = None
    ctx.comp = None
    return ctx


def _anon(action_type):
    node = MagicMock(spec=ActivityAnonTraversal)
    node.action_type = action_type.__name__
    node.action_type_cls = action_type
    return node


# ------- Simple action types for flow testing -------

@zdc.dataclass
class MyBuf(zdc.Buffer):
    data: int = 0


@zdc.dataclass
class SimpleComp(zdc.Component):
    pass


@zdc.dataclass
class IndepA(zdc.Action[SimpleComp]):
    async def body(self): pass


@zdc.dataclass
class IndepB(zdc.Action[SimpleComp]):
    async def body(self): pass


@zdc.dataclass
class IndepC(zdc.Action[SimpleComp]):
    async def body(self): pass


@zdc.dataclass
class Producer(zdc.Action[SimpleComp]):
    buf: MyBuf = zdc.flow_output()
    async def body(self): pass


@zdc.dataclass
class Consumer(zdc.Action[SimpleComp]):
    buf: MyBuf = zdc.flow_input()
    async def body(self): pass


@zdc.dataclass
class MidAction(zdc.Action[SimpleComp]):
    """Consumes from Producer and produces for Consumer2."""
    buf: MyBuf = zdc.flow_input()
    async def body(self): pass


# ---- Tests ----

def test_empty_stmts_returns_empty():
    ctx = _mock_ctx()
    graph = ScheduleGraph.build([], ctx)
    assert graph.stages() == []


def test_single_stmt_single_stage():
    ctx = _mock_ctx()
    stmts = [_anon(IndepA)]
    graph = ScheduleGraph.build(stmts, ctx)
    stages = graph.stages()
    assert len(stages) == 1
    assert len(stages[0]) == 1


def test_no_deps_single_stage():
    """Three independent actions → one stage with all three."""
    ctx = _mock_ctx()
    stmts = [_anon(IndepA), _anon(IndepB), _anon(IndepC)]
    graph = ScheduleGraph.build(stmts, ctx)
    stages = graph.stages()
    assert len(stages) == 1
    assert len(stages[0]) == 3


def test_single_dep_two_stages():
    """Producer→Consumer → stage 0 has producer, stage 1 has consumer."""
    ctx = _mock_ctx()
    stmts = [_anon(Producer), _anon(Consumer)]
    graph = ScheduleGraph.build(stmts, ctx)
    stages = graph.stages()
    assert len(stages) == 2
    # Producer in first stage, consumer in second
    assert stmts[0] in stages[0]
    assert stmts[1] in stages[1]


def test_cycle_detection_raises():
    """Cyclic dependency raises RuntimeError."""
    ctx = _mock_ctx()
    stmts = [_anon(IndepA), _anon(IndepB)]
    graph = ScheduleGraph.build(stmts, ctx)
    # Manually create a cycle
    graph._edges = [(0, 1), (1, 0)]
    with pytest.raises(RuntimeError, match="cyclic"):
        graph.stages()
