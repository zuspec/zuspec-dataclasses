"""Tests for P6 (method contract enforcement) from ASSERTION_ASSUMPTION_IMPL_PLAN.md.

Tests that ``with zdc.requires:`` / ``with zdc.ensures:`` blocks inside
``body()`` are enforced at runtime when ``ScenarioRunner(check_contracts=True)``.
"""
import asyncio

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.decorators import ContractViolation
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner
from zuspec.dataclasses.rt.contract_checker import _get_body_contracts, check_body_contracts


# ---------------------------------------------------------------------------
# Helper component and action types at module level (inspect.getsource needs this)
# ---------------------------------------------------------------------------

@zdc.dataclass
class _P6Comp(zdc.Component):
    pass


@zdc.dataclass
class _ActionBodyRequiresPass(zdc.Action[_P6Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    @zdc.constraint
    def bound_x(self):
        self.x > 0

    async def body(self):
        with zdc.requires:
            self.x > 0   # always true given bound_x above


@zdc.dataclass
class _ActionBodyRequiresFail(zdc.Action[_P6Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    @zdc.constraint
    def bound_x(self):
        self.x > 0

    async def body(self):
        with zdc.requires:
            self.x == 0   # never true (solver gives x > 0)


@zdc.dataclass
class _ActionBodyEnsuresPass(zdc.Action[_P6Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    async def body(self):
        self.x = 42
        with zdc.ensures:
            self.x == 42   # always true after body sets x=42


@zdc.dataclass
class _ActionBodyEnsuresFail(zdc.Action[_P6Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    async def body(self):
        self.x = 0
        with zdc.ensures:
            self.x > 0   # always false after body sets x=0


@zdc.dataclass
class _ActionBodyBothContracts(zdc.Action[_P6Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    @zdc.constraint
    def bound_x(self):
        self.x > 0

    async def body(self):
        with zdc.requires:
            self.x > 0
        # body doubles x
        self.x = self.x * 2
        with zdc.ensures:
            self.x > 0


@zdc.dataclass
class _ActionBodyNoContracts(zdc.Action[_P6Comp]):
    x: zdc.u8 = zdc.field(rand=True)

    async def body(self):
        self.x = 7


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(action_type, comp=None, check_contracts=True):
    if comp is None:
        comp = _P6Comp()

    async def _go():
        runner = ScenarioRunner(comp, seed=42, check_contracts=check_contracts)
        return await runner.run(action_type)

    return asyncio.run(_go())


# ---------------------------------------------------------------------------
# T-P6a: _get_body_contracts() (parsing / caching layer)
# ---------------------------------------------------------------------------

class TestGetBodyContracts:
    def test_no_contracts_returns_empty(self):
        contracts = _get_body_contracts(_ActionBodyNoContracts)
        assert contracts['requires'] == []
        assert contracts['ensures'] == []

    def test_requires_only_parsed(self):
        contracts = _get_body_contracts(_ActionBodyRequiresPass)
        assert len(contracts['requires']) >= 1
        assert contracts['ensures'] == []

    def test_ensures_only_parsed(self):
        contracts = _get_body_contracts(_ActionBodyEnsuresPass)
        assert contracts['requires'] == []
        assert len(contracts['ensures']) >= 1

    def test_both_contracts_parsed(self):
        contracts = _get_body_contracts(_ActionBodyBothContracts)
        assert len(contracts['requires']) >= 1
        assert len(contracts['ensures']) >= 1

    def test_caching_returns_same_lists(self):
        """Parsing should be cached: second call returns the same list objects."""
        c1 = _get_body_contracts(_ActionBodyBothContracts)
        c2 = _get_body_contracts(_ActionBodyBothContracts)
        assert c1['requires'] is c2['requires']
        assert c1['ensures'] is c2['ensures']

    def test_class_without_body_returns_empty(self):
        """Class with no body() at all returns empty contracts."""

        @zdc.dataclass
        class _NobodyComp(zdc.Component):
            pass

        @zdc.dataclass
        class _NoBodyAction(zdc.Action[_NobodyComp]):
            x: zdc.u8 = zdc.field(rand=True)
            # No body() — uses __activity__ or base body

        contracts = _get_body_contracts(_NoBodyAction)
        assert contracts['requires'] == []
        assert contracts['ensures'] == []


# ---------------------------------------------------------------------------
# T-P6b: Runtime enforcement via ScenarioRunner(check_contracts=True)
# ---------------------------------------------------------------------------

class TestBodyContractEnforcement:
    def test_requires_passes_when_satisfied(self):
        """Requires contract that holds — no exception."""
        action = _run(_ActionBodyRequiresPass)
        assert action.x > 0

    def test_requires_fails_when_violated(self):
        """Requires contract that cannot hold → ContractViolation before body."""
        with pytest.raises(ContractViolation) as exc_info:
            _run(_ActionBodyRequiresFail)
        assert exc_info.value.role == 'requires'
        assert 'body' in exc_info.value.method_name

    def test_ensures_passes_when_satisfied(self):
        """Ensures contract that holds after body — no exception."""
        action = _run(_ActionBodyEnsuresPass)
        assert action.x == 42

    def test_ensures_fails_when_violated(self):
        """Ensures contract that fails after body → ContractViolation."""
        with pytest.raises(ContractViolation) as exc_info:
            _run(_ActionBodyEnsuresFail)
        assert exc_info.value.role == 'ensures'
        assert 'body' in exc_info.value.method_name

    def test_both_contracts_pass(self):
        """Requires+ensures both hold — no exception, result is correct."""
        action = _run(_ActionBodyBothContracts)
        assert action.x > 0

    def test_no_contracts_no_exception(self):
        """Body with no contracts runs normally."""
        action = _run(_ActionBodyNoContracts)
        assert action.x == 7

    def test_no_check_contracts_suppresses_requires_violation(self):
        """Without check_contracts=True, requires violations are silent."""
        action = _run(_ActionBodyRequiresFail, check_contracts=False)
        # Body ran without raising — x is whatever solver gave (> 0)
        assert action.x > 0

    def test_no_check_contracts_suppresses_ensures_violation(self):
        """Without check_contracts=True, ensures violations are silent."""
        action = _run(_ActionBodyEnsuresFail, check_contracts=False)
        assert action.x == 0

    def test_contract_violation_has_correct_attrs(self):
        """ContractViolation exception carries role, method_name, expr_repr."""
        with pytest.raises(ContractViolation) as exc_info:
            _run(_ActionBodyEnsuresFail)
        cv = exc_info.value
        assert cv.role == 'ensures'
        assert 'body' in cv.method_name
        assert cv.expr_repr  # non-empty


# ---------------------------------------------------------------------------
# T-P6c: ContractChecker.wrap() (unit test)
# ---------------------------------------------------------------------------

class TestContractCheckerWrap:
    def test_wrap_disabled_returns_plain_method(self):
        """When check_contracts=False, wrap() returns the plain bound method."""
        from zuspec.dataclasses.rt.contract_checker import ContractChecker

        class _FakeAction:
            async def body(self):
                return 42

        inst = _FakeAction()
        checker = ContractChecker(check_contracts=False)
        wrapped = checker.wrap(type(inst).body, inst, ctx=None)
        # Should be the plain bound method
        import inspect
        assert inspect.iscoroutinefunction(wrapped)

    def test_wrap_enabled_returns_wrapper(self):
        """When check_contracts=True, wrap() returns a wrapper coroutine."""
        from zuspec.dataclasses.rt.contract_checker import ContractChecker
        import inspect

        class _FakeComp2:
            pass

        class _FakeAction2:
            async def body(self):
                return 99

        inst = _FakeAction2()
        checker = ContractChecker(check_contracts=True)
        # Need a minimal ActionContext-like object for ExprEval — use None as ctx
        # since there are no contract exprs on this body
        wrapped = checker.wrap(type(inst).body, inst, ctx=None)
        assert inspect.iscoroutinefunction(wrapped)
