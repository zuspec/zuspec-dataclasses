"""Tests for @constraint methods on Action classes being fed to the solver.

Classes must be at module level so inspect.getsource() can retrieve their source.
"""
import dataclasses
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.solver.api import randomize, randomize_with, RandomizationError


# ---------------------------------------------------------------------------
# Shared component
# ---------------------------------------------------------------------------

class MyComp(zdc.Component):
    pass


# ---------------------------------------------------------------------------
# Action with plain @constraint (alignment)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class AlignedWriteAction(zdc.Action[MyComp]):
    addr: zdc.u32 = zdc.field(rand=True, domain=(0, 0xFF))
    data: zdc.u32 = zdc.field(rand=True, domain=(0, 0xFFFF))

    @zdc.constraint
    def word_aligned(self):
        self.addr % 4 == 0


# ---------------------------------------------------------------------------
# Action with @constraint and domain
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class BoundedAction(zdc.Action[MyComp]):
    size: zdc.u32 = zdc.field(rand=True, domain=(1, 64))
    burst: zdc.u32 = zdc.field(rand=True, domain=(1, 8))

    @zdc.constraint
    def burst_fits(self):
        self.burst <= self.size


# ---------------------------------------------------------------------------
# Action with @constraint.requires (pre-condition)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class RequiresAction(zdc.Action[MyComp]):
    addr: zdc.u32 = zdc.field(rand=True, domain=(0, 0xFF))

    @zdc.constraint.requires
    def addr_not_zero(self):
        assert self.addr != 0


# ---------------------------------------------------------------------------
# Action with @constraint.ensures (post-condition — must NOT constrain solver)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class EnsuresOnlyAction(zdc.Action[MyComp]):
    value: zdc.u32 = zdc.field(rand=True, domain=(0, 10))

    @zdc.constraint.ensures
    def value_positive(self):
        assert self.value > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_action(cls):
    """Instantiate an action instance with defaults, no comp needed for solver."""
    action = object.__new__(cls)
    for f in dataclasses.fields(cls):
        if f.default is not dataclasses.MISSING:
            object.__setattr__(action, f.name, f.default)
        elif f.default_factory is not dataclasses.MISSING:
            object.__setattr__(action, f.name, f.default_factory())
        else:
            object.__setattr__(action, f.name, None)
    return action


# ---------------------------------------------------------------------------
# Tests: GAP1 — @constraint on Action feeds solver
# ---------------------------------------------------------------------------

class TestActionConstraintIR:
    """Verify that @constraint methods are collected into DataTypeAction.functions."""

    def test_constraint_functions_collected(self):
        from zuspec.dataclasses.data_model_factory import DataModelFactory
        factory = DataModelFactory()
        ctx = factory.build([MyComp, AlignedWriteAction])
        action_dt = ctx.type_m.get('AlignedWriteAction')
        assert action_dt is not None
        assert len(action_dt.functions) >= 1, (
            "Expected at least one constraint function in DataTypeAction.functions"
        )
        func_names = [f.name for f in action_dt.functions]
        assert 'word_aligned' in func_names

    def test_requires_constraint_collected(self):
        from zuspec.dataclasses.data_model_factory import DataModelFactory
        factory = DataModelFactory()
        ctx = factory.build([MyComp, RequiresAction])
        action_dt = ctx.type_m.get('RequiresAction')
        assert action_dt is not None
        func_names = [f.name for f in action_dt.functions]
        assert 'addr_not_zero' in func_names
        # Check role metadata preserved
        func = next(f for f in action_dt.functions if f.name == 'addr_not_zero')
        assert func.metadata.get('_constraint_role') == 'requires'

    def test_ensures_constraint_collected_but_solver_skips(self):
        """@ensures should appear in IR but be excluded from solver constraints."""
        from zuspec.dataclasses.data_model_factory import DataModelFactory
        from zuspec.dataclasses.solver.frontend.constraint_system_builder import (
            ConstraintSystemBuilder,
        )
        factory = DataModelFactory()
        ctx = factory.build([MyComp, EnsuresOnlyAction])
        action_dt = ctx.type_m.get('EnsuresOnlyAction')
        assert action_dt is not None
        func_names = [f.name for f in action_dt.functions]
        assert 'value_positive' in func_names

        # Build solver constraint system — ensures should NOT appear as constraint
        builder = ConstraintSystemBuilder()
        system = builder.build_from_struct(action_dt)
        # 'value' field is rand → a variable exists
        assert 'value' in system.variables
        # But no solver constraints should be generated (ensures is skipped)
        assert len(system.constraints) == 0, (
            "@constraint.ensures must not produce solver constraints"
        )


class TestActionConstraintSolver:
    """End-to-end: @constraint on Action actually constrains randomization."""

    def test_plain_constraint_constrains_solver(self):
        """@constraint on action constrains solver: burst <= size always."""
        action = _make_action(BoundedAction)
        violations = 0
        for _ in range(50):
            randomize(action)
            if action.burst > action.size:
                violations += 1
        assert violations == 0, (
            f"@constraint burst_fits violated {violations}/50 times — "
            "solver is ignoring action constraints"
        )

    def test_requires_constrains_solver(self):
        """@constraint.requires on action constrains solver: addr != 0 always."""
        action = _make_action(RequiresAction)
        zeros = 0
        for _ in range(50):
            randomize(action)
            if action.addr == 0:
                zeros += 1
        assert zeros == 0, (
            f"addr was 0 in {zeros}/50 randomizations — "
            "@constraint.requires should constrain the solver"
        )

    def test_ensures_does_not_constrain_solver(self):
        """@constraint.ensures must NOT constrain the solver."""
        action = _make_action(EnsuresOnlyAction)
        # domain=(0, 10) includes 0; if ensures incorrectly constrains the
        # solver we'd never see 0.
        values_seen = set()
        for _ in range(200):
            randomize(action)
            values_seen.add(action.value)
        assert 0 in values_seen, (
            "0 never generated — @constraint.ensures may be incorrectly "
            "constraining the solver"
        )

    def test_constraint_respects_domain(self):
        """Solver respects both domain= and @constraint simultaneously."""
        action = _make_action(AlignedWriteAction)
        for _ in range(30):
            randomize(action)
            assert 0 <= action.addr <= 0xFF, "domain not respected"

    def test_constraint_with_randomize_with(self):
        """Inline constraints combine with class @constraint."""
        action = _make_action(BoundedAction)
        for _ in range(20):
            with randomize_with(action):
                assert action.size >= 4
            # class constraint: burst <= size; inline: size >= 4
            assert action.burst <= action.size
            assert action.size >= 4

    def test_backend_caches_action_constraint_system(self):
        """Solver backend caches the constraint system for each action class."""
        import weakref
        from zuspec.dataclasses.solver.backend import python_backend

        # Clear any prior cache entry for this class
        python_backend._class_cache.pop(BoundedAction, None)

        action = _make_action(BoundedAction)
        randomize(action)  # first call — builds and caches

        assert BoundedAction in python_backend._class_cache, (
            "Action class not found in backend _class_cache after randomize"
        )
        cached_system = python_backend._class_cache[BoundedAction]

        randomize(action)  # second call — must use cache (same object)
        assert python_backend._class_cache[BoundedAction] is cached_system, (
            "Backend cache was replaced on second randomize call"
        )
