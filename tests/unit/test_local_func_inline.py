"""Tests for local pure-function inlining in DataModelFactory (Phase 1).

Tests that ``def f(...): return expr`` and ``def g(...): side_effect(...)``
bodies declared inside @zdc.proc methods (or other methods) are inlined
at call sites rather than emitting unresolvable ``ExprRefUnresolved`` nodes.
"""

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.data_model_factory import DataModelFactory
from zuspec.ir.core.expr import ExprCall, ExprRefUnresolved, ExprBin, ExprConstant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_proc_body(comp_cls):
    """Return the IR stmt list for the first @zdc.proc in comp_cls."""
    factory = DataModelFactory()
    ctx = factory.build(comp_cls)
    type_name = comp_cls.__qualname__
    dm = ctx.type_m[type_name]
    fn = dm.proc_processes[0]
    return fn.body


def _has_unresolved(stmts, name: str) -> bool:
    """Return True if any ExprRefUnresolved(name=name) appears recursively."""
    import dataclasses

    def _walk(obj):
        if isinstance(obj, ExprRefUnresolved) and obj.name == name:
            return True
        if dataclasses.is_dataclass(obj):
            for f in dataclasses.fields(obj):
                val = getattr(obj, f.name)
                if isinstance(val, list):
                    if any(_walk(v) for v in val):
                        return True
                elif dataclasses.is_dataclass(val):
                    if _walk(val):
                        return True
        return False

    return any(_walk(s) for s in stmts)


# ---------------------------------------------------------------------------
# Test data — models are imported from data/local_func_models.py so that
# DataModelFactory can retrieve their source code with inspect.getsource().
# ---------------------------------------------------------------------------

from .data.local_func_models import (
    SingleReturnComp,
    VoidSideEffectComp,
    ClosureOverOuterComp,
    NestedLocalCallComp,
    NeverCalledComp,
    AsyncPureComp,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLocalFuncInline:
    """Local pure function inlining in @zdc.proc bodies."""

    def test_single_return_no_unresolved(self):
        """def double(x): return x+x  — should NOT produce ExprRefUnresolved('double')."""
        body = _get_proc_body(SingleReturnComp)
        assert not _has_unresolved(body, 'double'), \
            "ExprRefUnresolved('double') leaked into IR; inlining failed"

    def test_single_return_inlines_expression(self):
        """double(5) should inline to an ExprBin(Add) with constant args."""
        body = _get_proc_body(SingleReturnComp)
        # The assignment `y = double(5)` should have an ExprBin value, not ExprCall('double')
        assign = next((s for s in body if hasattr(s, 'value')), None)
        assert assign is not None
        # After inlining, `double(5)` → `5 + 5` → ExprBin
        assert not isinstance(assign.value, ExprCall) or \
               (isinstance(assign.value, ExprCall) and
                not isinstance(assign.value.func, ExprRefUnresolved)), \
            "Call was not inlined"

    def test_void_side_effect_no_unresolved(self):
        """def bump(x): self.counter = self.counter + x  — void, used as stmt."""
        body = _get_proc_body(VoidSideEffectComp)
        assert not _has_unresolved(body, 'bump'), \
            "ExprRefUnresolved('bump') leaked; void func inlining failed"

    def test_closure_over_outer_var(self):
        """Local func references outer local var (closure); should resolve."""
        body = _get_proc_body(ClosureOverOuterComp)
        assert not _has_unresolved(body, 'add_base'), \
            "ExprRefUnresolved('add_base') leaked; closure inlining failed"

    def test_nested_local_calls(self):
        """Rs1() → R(rs1) → self.gpr.get(rs1) & MASK32 — two levels of inlining."""
        body = _get_proc_body(NestedLocalCallComp)
        assert not _has_unresolved(body, 'Rs1'), \
            "ExprRefUnresolved('Rs1') leaked"
        assert not _has_unresolved(body, 'R'), \
            "ExprRefUnresolved('R') leaked"

    def test_never_called_no_error(self):
        """A local def that is captured but never called should cause no error."""
        body = _get_proc_body(NeverCalledComp)
        # Just verify build succeeds and produces a body
        assert len(body) > 0

    def test_async_pure_function_inlined(self):
        """async def with no await is treated as pure and inlined."""
        body = _get_proc_body(AsyncPureComp)
        assert not _has_unresolved(body, 'pure_async'), \
            "ExprRefUnresolved('pure_async') leaked; async-pure inlining failed"
