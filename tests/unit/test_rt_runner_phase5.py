"""Phase 5 tests — tracer hooks, @extend, watchdog, ActivityConstraint."""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner, DeadlockError
from zuspec.dataclasses.rt.tracer import ActivityTracer
from zuspec.dataclasses.activity_dsl import do, constraint


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Minimal domain
# ---------------------------------------------------------------------------

@zdc.dataclass
class TracerComp(zdc.Component):
    pass


# ===========================================================================
# T5.3 — Tracer hooks
# ===========================================================================

class RecordingTracer(ActivityTracer):
    def __init__(self):
        self.events: list = []

    def action_start(self, action_type, comp, seed):
        self.events.append(("action_start", action_type))

    def action_solved(self, action):
        self.events.append(("action_solved", type(action)))

    def action_exec_begin(self, action):
        self.events.append(("action_exec_begin", type(action)))

    def action_exec_end(self, action):
        self.events.append(("action_exec_end", type(action)))

    def resource_lock(self, pool, instance_id):
        self.events.append(("resource_lock",))

    def resource_unlock(self, pool, instance_id):
        self.events.append(("resource_unlock",))


@zdc.dataclass
class TracerLeaf(zdc.Action[TracerComp]):
    async def body(self):
        pass


def test_action_start_called_once_per_traversal():
    tracer = RecordingTracer()
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0, tracer=tracer).run(TracerLeaf))
    starts = [e for e in tracer.events if e[0] == "action_start"]
    assert len(starts) == 1
    assert starts[0][1] is TracerLeaf


def test_action_solved_called_after_randomize():
    tracer = RecordingTracer()
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0, tracer=tracer).run(TracerLeaf))
    kinds = [e[0] for e in tracer.events]
    assert "action_solved" in kinds


def test_action_exec_begin_called():
    tracer = RecordingTracer()
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0, tracer=tracer).run(TracerLeaf))
    kinds = [e[0] for e in tracer.events]
    assert "action_exec_begin" in kinds


def test_action_exec_end_called():
    tracer = RecordingTracer()
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0, tracer=tracer).run(TracerLeaf))
    kinds = [e[0] for e in tracer.events]
    assert "action_exec_end" in kinds


def test_ordering_start_solved_begin_end():
    """Events must arrive in lifecycle order: start → solved → begin → end."""
    tracer = RecordingTracer()
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0, tracer=tracer).run(TracerLeaf))
    kinds = [e[0] for e in tracer.events]
    assert kinds.index("action_start") < kinds.index("action_solved")
    assert kinds.index("action_solved") < kinds.index("action_exec_begin")
    assert kinds.index("action_exec_begin") < kinds.index("action_exec_end")


def test_no_tracer_no_error():
    """Running without a tracer completes without error."""
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0).run(TracerLeaf))  # no tracer= kwarg


def test_custom_tracer_subclass():
    """User subclass overriding action_start receives the correct action_type."""
    seen = []

    class MyTracer(ActivityTracer):
        def action_start(self, action_type, comp, seed):
            seen.append(action_type)

    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0, tracer=MyTracer()).run(TracerLeaf))
    assert seen == [TracerLeaf]


def test_tracer_receives_comp_reference():
    """action_start receives the component bound to the action."""
    comps_seen = []

    class CompTracer(ActivityTracer):
        def action_start(self, action_type, comp, seed):
            comps_seen.append(comp)

    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0, tracer=CompTracer()).run(TracerLeaf))
    assert len(comps_seen) == 1
    assert isinstance(comps_seen[0], TracerComp)


@zdc.dataclass
class NestedLeaf(zdc.Action[TracerComp]):
    async def body(self): pass


@zdc.dataclass
class NestedOuter(zdc.Action[TracerComp]):
    async def activity(self):
        do(NestedLeaf)


def test_nested_traversal_events():
    """Compound action: events for both outer and inner traversals are fired."""
    tracer = RecordingTracer()
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0, tracer=tracer).run(NestedOuter))
    action_types = {e[1] for e in tracer.events if e[0] == "action_start"}
    assert NestedOuter in action_types
    assert NestedLeaf in action_types


# ===========================================================================
# T5.1 — @extend support
# ===========================================================================

_extend_log = []


@zdc.dataclass
class BaseLeafA(zdc.Action[TracerComp]):
    async def body(self):
        _extend_log.append("base_leaf_a")


@zdc.dataclass
class ExtLeafA(zdc.Action[TracerComp]):
    async def body(self):
        _extend_log.append("ext_leaf_a")


@zdc.dataclass
class BaseAction(zdc.Action[TracerComp]):
    async def activity(self):
        do(BaseLeafA)


@zdc.extend
class ExtAction(BaseAction):
    async def activity(self):
        do(ExtLeafA)


@zdc.dataclass
class ExtComp(zdc.Action[TracerComp]):
    async def activity(self):
        do(BaseAction)


def test_extend_single_extension_runs():
    """@extend body runs alongside base body."""
    _extend_log.clear()
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0).run(ExtComp))
    assert "base_leaf_a" in _extend_log
    assert "ext_leaf_a" in _extend_log


_extend2_log = []


@zdc.dataclass
class Base2LeafA(zdc.Action[TracerComp]):
    async def body(self):
        _extend2_log.append("base2_leaf")


@zdc.dataclass
class Ext2aLeaf(zdc.Action[TracerComp]):
    async def body(self):
        _extend2_log.append("ext2a_leaf")


@zdc.dataclass
class Ext2bLeaf(zdc.Action[TracerComp]):
    async def body(self):
        _extend2_log.append("ext2b_leaf")


@zdc.dataclass
class Base2Action(zdc.Action[TracerComp]):
    async def activity(self):
        do(Base2LeafA)


@zdc.extend
class Ext2aAction(Base2Action):
    async def activity(self):
        do(Ext2aLeaf)


@zdc.extend
class Ext2bAction(Base2Action):
    async def activity(self):
        do(Ext2bLeaf)


@zdc.dataclass
class Ext2Comp(zdc.Action[TracerComp]):
    async def activity(self):
        do(Base2Action)


def test_extend_two_extensions_run():
    """Two extensions: all three (base + 2 ext) bodies run."""
    _extend2_log.clear()
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0).run(Ext2Comp))
    assert "base2_leaf" in _extend2_log
    assert "ext2a_leaf" in _extend2_log
    assert "ext2b_leaf" in _extend2_log


@zdc.dataclass
class PlainLeaf(zdc.Action[TracerComp]):
    async def body(self):
        pass


@zdc.dataclass
class PlainOuter(zdc.Action[TracerComp]):
    async def activity(self):
        do(PlainLeaf)


def test_no_extend_runs_normally():
    """Action without @extend runs its body exactly once."""
    log = []
    original_body = PlainLeaf.body

    async def tracked_body(self):
        log.append("plain")
    PlainLeaf.body = tracked_body
    try:
        comp = TracerComp()
        _run(ScenarioRunner(comp, seed=0).run(PlainOuter))
        assert log == ["plain"]
    finally:
        PlainLeaf.body = original_body


# ===========================================================================
# T5.4 — Deadlock watchdog
# ===========================================================================

def test_deadlock_error_is_runtime_error():
    """DeadlockError inherits from RuntimeError."""
    assert issubclass(DeadlockError, RuntimeError)


@zdc.dataclass
class HangingAction(zdc.Action[TracerComp]):
    async def body(self):
        await asyncio.sleep(9999)  # never finishes


@zdc.dataclass
class HangOuter(zdc.Action[TracerComp]):
    async def activity(self):
        do(HangingAction)


def test_watchdog_fires_on_deadlock():
    """Task that never completes triggers DeadlockError within timeout."""
    comp = TracerComp()
    with pytest.raises(DeadlockError):
        _run(ScenarioRunner(comp, seed=0).run(HangOuter, timeout_s=0.1))


@zdc.dataclass
class FastAction(zdc.Action[TracerComp]):
    async def body(self):
        pass


@zdc.dataclass
class FastOuter(zdc.Action[TracerComp]):
    async def activity(self):
        do(FastAction)


def test_watchdog_does_not_fire_on_fast_completion():
    """Fast scenario completes before watchdog timeout."""
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0).run(FastOuter, timeout_s=10.0))  # no raise


# ===========================================================================
# T5.2 — ActivityConstraint infrastructure (no-crash tests)
# ===========================================================================

@zdc.dataclass
class ConstrainedLeaf(zdc.Action[TracerComp]):
    size: int = zdc.rand(domain=(0, 255))
    addr: int = zdc.rand(domain=(0, 255))
    async def body(self): pass


@zdc.dataclass
class ConstrainedOuter(zdc.Action[TracerComp]):
    a1: ConstrainedLeaf = None
    async def activity(self):
        await self.a1()
        with constraint():
            self.a1.size < 100


def test_activity_constraint_does_not_crash():
    """Activity with constraint block executes without error."""
    comp = TracerComp()
    # No crash — constraint infrastructure collects but doesn't error
    _run(ScenarioRunner(comp, seed=0).run(ConstrainedOuter))


@zdc.dataclass
class TwoHandleOuter(zdc.Action[TracerComp]):
    a1: ConstrainedLeaf = None
    a2: ConstrainedLeaf = None
    async def activity(self):
        await self.a1()
        await self.a2()
        with constraint():
            self.a1.addr != self.a2.addr


def test_activity_constraint_cross_action_no_crash():
    """Cross-action constraint block executes without error."""
    comp = TracerComp()
    _run(ScenarioRunner(comp, seed=0).run(TwoHandleOuter))
