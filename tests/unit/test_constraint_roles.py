"""Tests for P1 (decorator infrastructure), P2 (parser role capture),
P3 (context manager objects), and P5 (runtime role checking) from
ASSERTION_ASSUMPTION_IMPL_PLAN.md.
"""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.decorators import (
    _ConstraintDecorator, ContractViolation,
    _ContractContextManager, requires, ensures,
)
from zuspec.dataclasses.constraint_parser import ConstraintParser
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner


# ---------------------------------------------------------------------------
# T-P1: Decorator attribute tests
# ---------------------------------------------------------------------------

class TestRequiresDecorator:
    def test_requires_decorator_sets_role(self):
        @zdc.constraint.requires
        def my_c(self):
            self.x > 0

        assert my_c._is_constraint is True
        assert my_c._constraint_kind == 'fixed'
        assert my_c._constraint_role == 'requires'

    def test_ensures_decorator_sets_role(self):
        @zdc.constraint.ensures
        def my_c(self):
            self.x > 0

        assert my_c._is_constraint is True
        assert my_c._constraint_kind == 'fixed'
        assert my_c._constraint_role == 'ensures'

    def test_plain_constraint_role_is_none(self):
        @zdc.constraint
        def my_c(self):
            self.x > 0

        assert my_c._constraint_role is None

    def test_generic_constraint_role_is_none(self):
        @zdc.constraint.generic
        def my_c(self):
            self.x > 0

        assert my_c._constraint_role is None


class TestContractViolation:
    def test_contract_violation_exception_attrs(self):
        exc = ContractViolation('requires', 'Foo.bar', 'self.x > 0')
        assert exc.role == 'requires'
        assert exc.method_name == 'Foo.bar'
        assert exc.expr_repr == 'self.x > 0'

    def test_contract_violation_is_exception(self):
        exc = ContractViolation('ensures', 'A.b', 'expr')
        assert isinstance(exc, Exception)

    def test_contract_violation_message(self):
        exc = ContractViolation('requires', 'Dma.aligned', 'self.addr % 4 == 0')
        assert 'requires' in str(exc)
        assert 'Dma.aligned' in str(exc)


# ---------------------------------------------------------------------------
# T-P2: Parser role capture tests
# ---------------------------------------------------------------------------

class TestParserRoleCapture:
    def _make_cls(self):
        class Dummy:
            @zdc.constraint
            def plain(self):
                self.x > 0

            @zdc.constraint.requires
            def pre(self):
                self.x > 0

            @zdc.constraint.ensures
            def post(self):
                self.x < 100

        return Dummy

    def test_extract_constraints_includes_role(self):
        parser = ConstraintParser()
        constraints = parser.extract_constraints(self._make_cls())
        for c in constraints:
            assert 'role' in c

    def test_role_none_for_plain_constraint(self):
        parser = ConstraintParser()
        constraints = parser.extract_constraints(self._make_cls())
        plain = next(c for c in constraints if c['name'] == 'plain')
        assert plain['role'] is None

    def test_role_requires_for_requires(self):
        parser = ConstraintParser()
        constraints = parser.extract_constraints(self._make_cls())
        pre = next(c for c in constraints if c['name'] == 'pre')
        assert pre['role'] == 'requires'

    def test_role_ensures_for_ensures(self):
        parser = ConstraintParser()
        constraints = parser.extract_constraints(self._make_cls())
        post = next(c for c in constraints if c['name'] == 'post')
        assert post['role'] == 'ensures'

    def test_role_does_not_affect_expr_parsing(self):
        """Expression content is identical regardless of role."""
        class A:
            @zdc.constraint
            def c1(self):
                self.x > 5

        class B:
            @zdc.constraint.requires
            def c1(self):
                self.x > 5

        parser = ConstraintParser()
        ca = parser.extract_constraints(A)[0]
        cb = parser.extract_constraints(B)[0]
        assert ca['exprs'] == cb['exprs']


# ---------------------------------------------------------------------------
# T-P3: Context manager tests
# ---------------------------------------------------------------------------

class TestContextManagers:
    def test_requires_context_manager_is_noop(self):
        with zdc.requires:
            1 == 1  # noqa: B015

    def test_ensures_context_manager_is_noop(self):
        with zdc.ensures:
            1 == 1  # noqa: B015

    def test_requires_context_manager_does_not_suppress_exception(self):
        with pytest.raises(RuntimeError):
            with zdc.requires:
                raise RuntimeError("test")

    def test_ensures_context_manager_does_not_suppress_exception(self):
        with pytest.raises(ValueError):
            with zdc.ensures:
                raise ValueError("test")

    def test_requires_is_contract_context_manager(self):
        assert isinstance(zdc.requires, _ContractContextManager)
        assert zdc.requires._role == 'requires'

    def test_ensures_is_contract_context_manager(self):
        assert isinstance(zdc.ensures, _ContractContextManager)
        assert zdc.ensures._role == 'ensures'

    def test_zdc_requires_exported(self):
        import zuspec.dataclasses as m
        assert hasattr(m, 'requires')

    def test_zdc_ensures_exported(self):
        import zuspec.dataclasses as m
        assert hasattr(m, 'ensures')


# ---------------------------------------------------------------------------
# T-P5: Runtime role checking — @constraint.requires / @constraint.ensures
# ---------------------------------------------------------------------------

# Module-level action classes so inspect.getsource works in ConstraintParser.

@zdc.dataclass
class _P5Comp(zdc.Component):
    pass


@zdc.dataclass
class _ActionWithRequires(zdc.Action[_P5Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    @zdc.constraint
    def bound_x(self):
        self.x > 0

    @zdc.constraint.requires
    def pre_x_positive(self):
        assert self.x > 0

    async def body(self):
        pass


@zdc.dataclass
class _ActionWithEnsures(zdc.Action[_P5Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    @zdc.constraint
    def bound_x(self):
        self.x > 0

    @zdc.constraint.ensures
    def post_x_positive(self):
        assert self.x > 0

    async def body(self):
        pass


@zdc.dataclass
class _ActionEnsuresViolated(zdc.Action[_P5Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    @zdc.constraint
    def bound_x(self):
        self.x > 0

    @zdc.constraint.ensures
    def post_x_must_stay_positive(self):
        # After body runs, x is 0, so this ensures always fails.
        assert self.x > 0

    async def body(self):
        # Deliberately violate the ensures postcondition
        self.x = 0


@zdc.dataclass
class _ActionRequiresViolated(zdc.Action[_P5Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    @zdc.constraint.requires
    def pre_x_must_be_99(self):
        # Solver doesn't know about this; it won't always satisfy it.
        assert self.x == 99

    async def body(self):
        pass


class TestP5RuntimeRoleChecking:
    """T-P5: ScenarioRunner.check_contracts triggers ContractViolation."""

    def _run(self, action_type, comp, check_contracts=True):
        async def _go():
            runner = ScenarioRunner(comp, seed=42, check_contracts=check_contracts)
            return await runner.run(action_type)
        return asyncio.run(_go())

    def test_requires_role_passes_when_satisfied(self):
        """@constraint.requires that holds should not raise."""
        comp = _P5Comp()
        # bound_x ensures x > 0, so pre_x_positive should pass
        action = self._run(_ActionWithRequires, comp)
        assert action.x > 0

    def test_ensures_role_passes_when_satisfied(self):
        """@constraint.ensures that holds should not raise."""
        comp = _P5Comp()
        action = self._run(_ActionWithEnsures, comp)
        assert action.x > 0

    def test_ensures_violation_raises_contract_violation(self):
        """@constraint.ensures that fails → ContractViolation."""
        comp = _P5Comp()
        with pytest.raises(ContractViolation) as exc_info:
            self._run(_ActionEnsuresViolated, comp)
        assert exc_info.value.role == 'ensures'

    def test_no_check_contracts_suppresses_ensures_violation(self):
        """Without check_contracts=True, ensures violations are silent."""
        comp = _P5Comp()
        # Should not raise even though ensures is violated
        action = self._run(_ActionEnsuresViolated, comp, check_contracts=False)
        assert action.x == 0

    def test_contract_violation_exception_attributes(self):
        """ContractViolation carries role, method_name, expr_repr."""
        comp = _P5Comp()
        with pytest.raises(ContractViolation) as exc_info:
            self._run(_ActionEnsuresViolated, comp)
        cv = exc_info.value
        assert cv.role == 'ensures'
        assert 'post_x_must_stay_positive' in cv.method_name
        assert cv.expr_repr  # non-empty

    def test_ensures_not_injected_into_solver(self):
        """@constraint.ensures should NOT constrain the solver's solution."""
        comp = _P5Comp()
        # _ActionEnsuresViolated.post_x_must_stay_positive says x > 0,
        # but body zeros x. The ensures constraint is NOT injected into the solver,
        # so the solver can still find a satisfying assignment.
        # Run WITHOUT check_contracts to just observe behavior.
        action = self._run(_ActionEnsuresViolated, comp, check_contracts=False)
        # body zeroed x — that's expected
        assert action.x == 0

    def test_scenario_runner_check_contracts_flag(self):
        """ScenarioRunner accepts check_contracts kwarg."""
        comp = _P5Comp()
        runner = ScenarioRunner(comp, seed=1, check_contracts=True)
        assert runner._check_contracts is True

    def test_scenario_runner_default_no_contracts(self):
        """ScenarioRunner defaults to check_contracts=False."""
        comp = _P5Comp()
        runner = ScenarioRunner(comp, seed=1)
        assert runner._check_contracts is False
