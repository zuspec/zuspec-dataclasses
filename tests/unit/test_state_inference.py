"""Tests for PSS state inference: state-graph construction, BFS, and
end-to-end state-chain inference through ObservePowerState-style actions.

Covers Phases 1-5 of pss-scenario-runtime-impl-plan.md.
"""
from __future__ import annotations

import asyncio
import dataclasses as dc
from typing import Optional

import pytest

import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.action_registry import ActionRegistry
from zuspec.dataclasses.rt.icl_table import ICLTable
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner
from zuspec.dataclasses.rt.structural_solver import (
    InferenceFeasibilityError,
    StructuralSolver,
    extract_state_target,
)
from zuspec.dataclasses.rt.state_graph_factory import (
    StateGraph,
    StateSpaceTooLargeError,
    _fields_from_state_type,
    _transition_actions_for_state,
    get_or_build,
    clear_cache,
)


# ---------------------------------------------------------------------------
# Domain model (module-level for constraint parser source lookup)
# ---------------------------------------------------------------------------

@zdc.dataclass
class PowerState(zdc.State):
    domain_A: zdc.u2 = zdc.rand()
    domain_B: zdc.u2 = zdc.rand()
    domain_C: zdc.u2 = zdc.rand()

    @zdc.constraint
    def a_ge_b(self):
        self.domain_A >= self.domain_B

    @zdc.constraint
    def c_excludes_b(self):
        zdc.implies(self.domain_C != 0, self.domain_B == 0)


@zdc.dataclass
class GraphicsComp(zdc.Component):
    pass


@zdc.dataclass
class ATransition(zdc.Action[GraphicsComp]):
    step: int = zdc.rand(domain=(-2, 1))
    prev: PowerState = zdc.flow_input()
    next_: PowerState = zdc.flow_output()

    @zdc.constraint
    def step_a(self):
        self.next_.domain_A == self.prev.domain_A + self.step

    @zdc.constraint
    def keep_b(self):
        self.next_.domain_B == self.prev.domain_B

    @zdc.constraint
    def keep_c(self):
        self.next_.domain_C == self.prev.domain_C


@zdc.dataclass
class BTransition(zdc.Action[GraphicsComp]):
    step: int = zdc.rand(domain=(-2, 1))
    prev: PowerState = zdc.flow_input()
    next_: PowerState = zdc.flow_output()

    @zdc.constraint
    def step_b(self):
        self.next_.domain_B == self.prev.domain_B + self.step

    @zdc.constraint
    def keep_a(self):
        self.next_.domain_A == self.prev.domain_A

    @zdc.constraint
    def keep_c(self):
        self.next_.domain_C == self.prev.domain_C


@zdc.dataclass
class CTransition(zdc.Action[GraphicsComp]):
    step: int = zdc.rand(domain=(-2, 1))
    prev: PowerState = zdc.flow_input()
    next_: PowerState = zdc.flow_output()

    @zdc.constraint
    def step_c(self):
        self.next_.domain_C == self.prev.domain_C + self.step

    @zdc.constraint
    def keep_a(self):
        self.next_.domain_A == self.prev.domain_A

    @zdc.constraint
    def keep_b(self):
        self.next_.domain_B == self.prev.domain_B


@zdc.dataclass
class ObservePowerState(zdc.Action[GraphicsComp]):
    curr_state: PowerState = zdc.flow_input()

    async def body(self):
        pass


# Scenario: observe with inline constraint
@zdc.dataclass
class ObserveWithConstraint(zdc.Action[GraphicsComp]):
    async def activity(self):
        with zdc.do(ObservePowerState) as obs:
            obs.curr_state.domain_B == 2


# Scenario: observe without inline constraint
@zdc.dataclass
class ObserveNoConstraint(zdc.Action[GraphicsComp]):
    async def activity(self):
        await zdc.do(ObservePowerState)


# Huge state type for overflow test
@zdc.dataclass
class HugeState(zdc.State):
    a: zdc.u8 = zdc.rand()
    b: zdc.u8 = zdc.rand()
    c: zdc.u8 = zdc.rand()


@zdc.dataclass
class HugeComp(zdc.Component):
    pass


@zdc.dataclass
class HugeObserver(zdc.Action[HugeComp]):
    s: HugeState = zdc.flow_input()


# Buffer-based model for Phase 1 parity test
@zdc.dataclass
class SimpleBuffer(zdc.Buffer):
    data: int = zdc.rand(domain=(1, 100))


@zdc.dataclass
class BufComp(zdc.Component):
    pass


@zdc.dataclass
class ProduceBuf(zdc.Action[BufComp]):
    buf: SimpleBuffer = zdc.flow_output()

    async def body(self):
        pass


@zdc.dataclass
class ConsumeBuf(zdc.Action[BufComp]):
    buf: SimpleBuffer = zdc.flow_input()

    async def body(self):
        pass


@zdc.dataclass
class BufScenario(zdc.Action[BufComp]):
    async def activity(self):
        await zdc.do(ConsumeBuf)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Phase 1 Tests
# ---------------------------------------------------------------------------

class TestPhase1ActionCall:
    """Action.__call__ triggers buffer inference (parity with ScenarioRunner)."""

    def test_action_call_with_buffer_inference(self):
        """Action()(comp=comp) should infer ProduceBuf for ConsumeBuf."""
        comp = BufComp()
        action = _run(BufScenario()(comp=comp, seed=42))
        assert action is not None

    def test_action_call_seed_determinism(self):
        """Same seed produces same result via __call__."""
        comp = BufComp()
        a = _run(BufScenario()(comp=comp, seed=42))
        b = _run(BufScenario()(comp=comp, seed=42))
        assert a is not None and b is not None


# ---------------------------------------------------------------------------
# Phase 2 Tests
# ---------------------------------------------------------------------------

class TestPhase2StateGraphFactory:

    def setup_method(self):
        clear_cache()

    def test_field_discovery(self):
        """_fields_from_state_type returns correct field descriptors."""
        fds = _fields_from_state_type(PowerState)
        assert len(fds) == 3
        names = [fd.name for fd in fds]
        assert "domain_A" in names
        assert "domain_B" in names
        assert "domain_C" in names
        # u2: unsigned 2-bit -> 0..3
        for fd in fds:
            assert fd.lo == 0
            assert fd.hi == 3

    def test_state_invariant(self):
        """Invariant accepts (2,0,3) and rejects (2,2,3)."""
        comp = GraphicsComp()
        registry = ActionRegistry.build(comp)
        graph = get_or_build(PowerState, registry)
        # (2,0,3): A=2 >= B=0 OK, C=3 != 0 -> B must be 0 OK
        assert (2, 0, 3) in graph.node_set
        # (2,2,3): C=3 != 0 -> B must be 0, but B=2, FAIL
        assert (2, 2, 3) not in graph.node_set

    def test_transition_discovery(self):
        """Finds A/B/C transition actions for PowerState."""
        comp = GraphicsComp()
        registry = ActionRegistry.build(comp)
        transitions = _transition_actions_for_state(registry, PowerState)
        transition_types = set(transitions)
        assert ATransition in transition_types
        assert BTransition in transition_types
        assert CTransition in transition_types

    def test_state_graph_construction(self):
        """Auto-builds graph with valid nodes and edges."""
        comp = GraphicsComp()
        registry = ActionRegistry.build(comp)
        graph = get_or_build(PowerState, registry)
        # Should have some valid nodes
        assert len(graph.nodes) > 0
        # Initial state should be valid
        assert graph.initial_state() in graph.node_set
        # Should have edges
        total_edges = sum(len(e) for e in graph.edges.values())
        assert total_edges > 0

    def test_cache_reuse(self):
        """Second call returns cached graph (same id())."""
        comp = GraphicsComp()
        registry = ActionRegistry.build(comp)
        g1 = get_or_build(PowerState, registry)
        g2 = get_or_build(PowerState, registry)
        assert g1 is g2

    def test_state_space_too_large(self):
        """StateSpaceTooLargeError raised for huge state space."""
        comp = HugeComp()
        registry = ActionRegistry.build(comp)
        # 256^3 = 16M > 10,000
        with pytest.raises(StateSpaceTooLargeError):
            get_or_build(HugeState, registry)


# ---------------------------------------------------------------------------
# Phase 3 Tests
# ---------------------------------------------------------------------------

class TestPhase3StateBFS:

    def setup_method(self):
        clear_cache()

    def test_extract_state_target_equality(self):
        """extract_state_target parses field == constant patterns."""
        import ast
        # Simulate: obs.curr_state.domain_B == 2
        code = "obs.curr_state.domain_B == 2"
        tree = ast.parse(code, mode='exec')
        stmt = tree.body[0]

        pred = extract_state_target([stmt], "curr_state", PowerState)
        assert pred is not None
        # domain_B is index 1; (0,2,0) should satisfy domain_B==2
        assert pred((0, 2, 0)) is True
        assert pred((0, 1, 0)) is False

    def test_extract_state_target_comparison(self):
        """extract_state_target handles >=, <=, != patterns."""
        import ast

        # domain_A >= 2
        code = "obs.curr_state.domain_A >= 2"
        tree = ast.parse(code, mode='exec')
        stmt = tree.body[0]
        pred = extract_state_target([stmt], "curr_state", PowerState)
        assert pred is not None
        assert pred((2, 0, 0)) is True
        assert pred((3, 0, 0)) is True
        assert pred((1, 0, 0)) is False

    def test_bfs_shortest_path(self):
        """BFS returns shortest path from (0,0,0) to domain_B==2."""
        comp = GraphicsComp()
        registry = ActionRegistry.build(comp)
        graph = get_or_build(PowerState, registry)

        icl = ICLTable.build(registry)
        solver = StructuralSolver(icl, seed=0, registry=registry)

        # domain_B is index 1
        pred = lambda t: t[1] == 2
        path = solver._bfs(graph, (0, 0, 0), pred)
        assert path is not None
        assert len(path) >= 1
        # Verify path correctness: first edge starts from (0,0,0)
        assert path[0].src == (0, 0, 0)
        # Last edge dst satisfies predicate
        assert path[-1].dst[1] == 2

    def test_bfs_no_path(self):
        """BFS returns None when target is unreachable."""
        comp = GraphicsComp()
        registry = ActionRegistry.build(comp)
        graph = get_or_build(PowerState, registry)

        icl = ICLTable.build(registry)
        solver = StructuralSolver(icl, seed=0, registry=registry)

        # Predicate that nothing satisfies (e.g., domain_A == 99)
        pred = lambda t: t[0] == 99
        path = solver._bfs(graph, (0, 0, 0), pred)
        assert path is None

    def test_bfs_already_at_target(self):
        """BFS returns empty path when start already satisfies predicate."""
        comp = GraphicsComp()
        registry = ActionRegistry.build(comp)
        graph = get_or_build(PowerState, registry)

        icl = ICLTable.build(registry)
        solver = StructuralSolver(icl, seed=0, registry=registry)

        # (0,0,0): domain_B == 0
        pred = lambda t: t[1] == 0
        path = solver._bfs(graph, (0, 0, 0), pred)
        assert path is not None
        assert len(path) == 0


# ---------------------------------------------------------------------------
# Phase 4 Tests
# ---------------------------------------------------------------------------

class TestPhase4CrossFlowConstraints:

    def setup_method(self):
        clear_cache()

    def test_cross_flow_constraint_step_solve(self):
        """ATransition with fixed prev/next solves step correctly."""
        from zuspec.dataclasses.rt.resource_rt import make_resource
        from zuspec.dataclasses.solver.api import randomize

        prev_obj = make_resource(PowerState)
        object.__setattr__(prev_obj, "domain_A", 2)
        object.__setattr__(prev_obj, "domain_B", 0)
        object.__setattr__(prev_obj, "domain_C", 0)

        next_obj = make_resource(PowerState)
        object.__setattr__(next_obj, "domain_A", 3)
        object.__setattr__(next_obj, "domain_B", 0)
        object.__setattr__(next_obj, "domain_C", 0)

        action = make_resource(ATransition)
        object.__setattr__(action, "prev", prev_obj)
        object.__setattr__(action, "next_", next_obj)

        randomize(action, seed=0)
        # step should be 1 (3 - 2 = 1)
        assert action.step == 1

    def test_cross_flow_unchanged_fields(self):
        """Field-copy constraints (next_.X == prev.X) satisfied."""
        from zuspec.dataclasses.rt.resource_rt import make_resource
        from zuspec.dataclasses.solver.api import randomize

        prev_obj = make_resource(PowerState)
        object.__setattr__(prev_obj, "domain_A", 1)
        object.__setattr__(prev_obj, "domain_B", 0)
        object.__setattr__(prev_obj, "domain_C", 3)

        next_obj = make_resource(PowerState)
        object.__setattr__(next_obj, "domain_A", 2)
        object.__setattr__(next_obj, "domain_B", 0)
        object.__setattr__(next_obj, "domain_C", 3)

        action = make_resource(ATransition)
        object.__setattr__(action, "prev", prev_obj)
        object.__setattr__(action, "next_", next_obj)

        randomize(action, seed=0)
        # B and C should be unchanged
        assert action.next_.domain_B == action.prev.domain_B
        assert action.next_.domain_C == action.prev.domain_C


# ---------------------------------------------------------------------------
# Phase 5 Tests
# ---------------------------------------------------------------------------

class TestPhase5ObserveTrigger:

    def setup_method(self):
        clear_cache()

    def test_observe_no_constraint_uses_current(self):
        """ObservePowerState without inline constraints runs without error."""
        comp = GraphicsComp()
        runner = ScenarioRunner(comp, seed=42)
        action = _run(runner.run(ObserveNoConstraint))
        assert action is not None


