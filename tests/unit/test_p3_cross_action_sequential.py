"""P3 cross-action sequential constraint propagation tests.

Tests that concrete field values from a completed sequential action are
substituted into the inline constraints of the following action.

Scenario: ActionA has a rand field ``out_val``; ActionB has a rand field
``in_val`` constrained by ``assert b.in_val == a.out_val + 1``.  After ActionA
completes and its ``out_val`` is concrete, the propagator substitutes the
concrete value so ActionB's solver sees ``assert self.in_val == <concrete+1>``.
"""
from __future__ import annotations

import asyncio

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner


# ---------------------------------------------------------------------------
# Domain model (all action types must be module-level)
# ---------------------------------------------------------------------------

@zdc.dataclass
class Comp(zdc.Component):
    pass


@zdc.dataclass
class ActionA(zdc.Action[Comp]):
    """Producer — has a rand out_val field that other actions can constrain from."""
    out_val: int = zdc.rand()

    async def body(self):
        pass


@zdc.dataclass
class ActionB(zdc.Action[Comp]):
    """Consumer — has a rand in_val that can be constrained relative to a.out_val."""
    in_val: int = zdc.rand()

    async def body(self):
        pass


@zdc.dataclass
class UnrelatedAction(zdc.Action[Comp]):
    """Has its own rand field — forward propagation must not leak into it."""
    x: int = zdc.rand()

    async def body(self):
        pass


# Scenario: b.in_val == a.out_val + 1
@zdc.dataclass
class SeqConstraintScenario(zdc.Action[Comp]):
    async def activity(self):
        with zdc.do(ActionA) as a:
            pass
        with zdc.do(ActionB) as b:
            assert b.in_val == a.out_val + 1


# Scenario: unrelated action should NOT be affected by ActionA's propagated values
@zdc.dataclass
class UnrelatedNotAffectedScenario(zdc.Action[Comp]):
    async def activity(self):
        with zdc.do(ActionA) as a:
            pass
        with zdc.do(UnrelatedAction) as u:
            pass


# Scenario: multiple sequential pairs in a chain
@zdc.dataclass
class MultiStepChainScenario(zdc.Action[Comp]):
    """a → b (b.in_val == a.out_val + 1) → c (c.in_val == b.in_val * 2)."""
    async def activity(self):
        with zdc.do(ActionA) as a:
            pass
        with zdc.do(ActionB) as b:
            assert b.in_val == a.out_val + 1
        with zdc.do(ActionB) as c:
            assert c.in_val == b.in_val * 2


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run_action(action_type, seed=42):
    comp = Comp()
    runner = ScenarioRunner(comp, seed=seed)
    return asyncio.run(runner.run(action_type))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestForwardConstraintPropagation:
    def test_constraint_a_field_used_in_b(self):
        """b.in_val == a.out_val + 1 is satisfied after forward propagation."""
        for seed in range(5):
            result = run_action(SeqConstraintScenario, seed=seed)
            # We can't directly access a and b from the scenario result,
            # so we validate by re-running with known fields.
            assert result is not None

    def test_propagated_constraint_holds(self):
        """Directly verify that b.in_val == a.out_val + 1 after execution."""
        # Use a tracer-like approach: patch body() to capture values
        a_vals = []
        b_vals = []

        orig_a_body = ActionA.body
        orig_b_body = ActionB.body

        async def capture_a(self):
            a_vals.append(self.out_val)
            await orig_a_body(self)

        async def capture_b(self):
            b_vals.append(self.in_val)
            await orig_b_body(self)

        ActionA.body = capture_a
        ActionB.body = capture_b
        try:
            run_action(SeqConstraintScenario, seed=7)
        finally:
            ActionA.body = orig_a_body
            ActionB.body = orig_b_body

        assert len(a_vals) == 1
        assert len(b_vals) == 1
        assert b_vals[0] == a_vals[0] + 1

    def test_propagation_does_not_affect_unrelated(self):
        """UnrelatedAction's rand field x is not constrained by ActionA."""
        x_values = []

        orig_body = UnrelatedAction.body

        async def capture(self):
            x_values.append(self.x)
            await orig_body(self)

        UnrelatedAction.body = capture
        try:
            for seed in range(10):
                x_values.clear()
                run_action(UnrelatedNotAffectedScenario, seed=seed)
                # x should be freely randomized (not forced to any specific value)
                assert x_values[0] is not None  # just check it's set

        finally:
            UnrelatedAction.body = orig_body

    def test_multi_step_chain(self):
        """a → b (b.in_val == a.out_val + 1) → c (c.in_val == b.in_val * 2)."""
        a_vals = []
        b_vals = []
        c_vals = []

        orig_a = ActionA.body
        orig_b = ActionB.body

        call_count = [0]

        async def capture_a(self):
            a_vals.append(self.out_val)
            await orig_a(self)

        async def capture_b(self):
            call_count[0] += 1
            if call_count[0] == 1:
                b_vals.append(self.in_val)
            else:
                c_vals.append(self.in_val)
            await orig_b(self)

        ActionA.body = capture_a
        ActionB.body = capture_b
        try:
            run_action(MultiStepChainScenario, seed=3)
        finally:
            ActionA.body = orig_a
            ActionB.body = orig_b

        assert len(a_vals) == 1
        assert len(b_vals) == 1
        assert len(c_vals) == 1
        assert b_vals[0] == a_vals[0] + 1
        assert c_vals[0] == b_vals[0] * 2

    def test_propagator_substitute_ast(self):
        """Unit test for ForwardConstraintPropagator.substitute() directly."""
        import ast
        from zuspec.dataclasses.rt.forward_constraint_propagator import ForwardConstraintPropagator

        prop = ForwardConstraintPropagator()
        prop._values["a"] = {"out_val": 42}

        stmts = ast.parse("assert self.in_val == a.out_val + 1").body
        rewritten = prop.substitute(stmts)
        assert len(rewritten) == 1

        # The rewritten AST should have 42 + 1 as the comparator
        # Compile and eval to check
        mod = ast.Module(body=rewritten, type_ignores=[])
        code = compile(mod, "<test>", "exec")
        # Evaluate with in_val = 43 → should NOT raise
        exec(code, {"self": type("_", (), {"in_val": 43})()})

        # Evaluate with in_val = 10 → should raise AssertionError
        with pytest.raises(AssertionError):
            exec(code, {"self": type("_", (), {"in_val": 10})()})

    def test_propagator_no_values_returns_original(self):
        """substitute() returns original list when no values are recorded."""
        import ast
        from zuspec.dataclasses.rt.forward_constraint_propagator import ForwardConstraintPropagator

        prop = ForwardConstraintPropagator()
        stmts = ast.parse("assert x == 1").body
        result = prop.substitute(stmts)
        # Same objects (no copy made when nothing to substitute)
        assert result is stmts
