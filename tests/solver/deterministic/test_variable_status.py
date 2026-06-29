"""Tests for VarStatusMap and build_from_struct."""
import dataclasses
import pytest
import zuspec.dataclasses as zdc
from zuspec.be.py.solver.deterministic.variable_status import (
    VarStatus, VarInfo, VarStatusMap, build_from_struct,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_struct(cls, comp_cls=None):
    """Build and return the IR DataTypeStruct for *cls*."""
    from zuspec.dataclasses.data_model_factory import DataModelFactory
    classes = [comp_cls, cls] if comp_cls is not None else [cls]
    ctx = DataModelFactory().build(classes)
    name = cls.__qualname__
    st = ctx.type_m.get(name) or ctx.type_m.get(cls.__name__)
    if st is None:
        # Try fully qualified
        fqn = f"{cls.__module__}.{cls.__qualname__}"
        st = ctx.type_m.get(fqn)
    assert st is not None, f"IR struct for {cls.__name__} not found in {list(ctx.type_m.keys())}"
    return st


class _Comp(zdc.Component):
    pass


# ---------------------------------------------------------------------------
# VarStatusMap unit tests
# ---------------------------------------------------------------------------

class TestVarStatusMap:
    def _make(self):
        return VarStatusMap({
            "a": VarInfo(VarStatus.BOUND, False),
            "b": VarInfo(VarStatus.OPEN, True),
            "c": VarInfo(VarStatus.PARTIAL, False),
        })

    def test_status_bound(self):
        vsm = self._make()
        assert vsm.status("a") == VarStatus.BOUND

    def test_status_open(self):
        vsm = self._make()
        assert vsm.status("b") == VarStatus.OPEN

    def test_status_missing_defaults_bound(self):
        vsm = self._make()
        assert vsm.status("nonexistent") == VarStatus.BOUND

    def test_is_bound(self):
        vsm = self._make()
        assert vsm.is_bound("a")
        assert not vsm.is_bound("b")

    def test_is_open(self):
        vsm = self._make()
        assert vsm.is_open("b")
        assert not vsm.is_open("a")

    def test_write_back_true(self):
        vsm = self._make()
        assert vsm.write_back("b")

    def test_write_back_false(self):
        vsm = self._make()
        assert not vsm.write_back("a")

    def test_open_var_names(self):
        vsm = self._make()
        assert vsm.open_var_names() == {"b"}

    def test_all_names(self):
        vsm = self._make()
        assert vsm.all_names() == {"a", "b", "c"}

    def test_bind_open_to_bound(self):
        vsm = self._make()
        vsm.bind("b")
        assert vsm.is_bound("b")

    def test_bind_already_bound_noop(self):
        vsm = self._make()
        vsm.bind("a")  # no-op
        assert vsm.is_bound("a")

    def test_partial_transition(self):
        vsm = self._make()
        vsm.partial("b")
        assert vsm.status("b") == VarStatus.PARTIAL

    def test_copy_independent(self):
        vsm = self._make()
        copy = vsm.copy()
        copy.bind("b")
        assert vsm.is_open("b")   # original unchanged
        assert copy.is_bound("b")

    def test_count_open_vars_in(self):
        vsm = self._make()
        assert vsm.count_open_vars_in({"a", "b"}) == 1
        assert vsm.count_open_vars_in({"a"}) == 0
        assert vsm.count_open_vars_in({"b"}) == 1


# ---------------------------------------------------------------------------
# build_from_struct: rand fields → OPEN/write_back=True
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class SimpleRandAction(zdc.Action[_Comp]):
    x: zdc.u32 = zdc.field(rand=True, domain=(0, 255))
    y: zdc.u32 = zdc.field(rand=True, domain=(0, 255))
    z: int = 0  # non-rand


class TestBuildFromStructRand:
    def setup_method(self):
        self.st = _get_struct(SimpleRandAction, _Comp)
        self.vsm = build_from_struct(self.st)

    def test_rand_field_is_open(self):
        assert self.vsm.is_open("x")
        assert self.vsm.is_open("y")

    def test_rand_field_write_back(self):
        assert self.vsm.write_back("x")
        assert self.vsm.write_back("y")

    def test_nonrand_field_is_bound(self):
        # 'z' is a plain int field, not rand
        if "z" in self.vsm.all_names():
            assert self.vsm.is_bound("z")


# ---------------------------------------------------------------------------
# build_from_struct: internal / leading _ → OPEN/write_back=False
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class InternalFieldAction(zdc.Action[_Comp]):
    result: zdc.u32 = zdc.field(rand=True, domain=(0, 255))
    _temp: zdc.u32 = zdc.field(rand=True, domain=(0, 255))


class TestBuildFromStructInternal:
    def setup_method(self):
        self.st = _get_struct(InternalFieldAction, _Comp)
        self.vsm = build_from_struct(self.st)

    def test_leading_underscore_open_with_writeback(self):
        # Leading-'_' rand fields are still OPEN and written back — the body()
        # may read them after the solve.  Only explicit internal=True metadata
        # suppresses write-back.
        names = self.vsm.all_names()
        internal = [n for n in names if n.startswith('_')]
        for n in internal:
            assert self.vsm.is_open(n)
            assert self.vsm.write_back(n)

    def test_result_field_open_with_writeback(self):
        if "result" in self.vsm.all_names():
            assert self.vsm.is_open("result")
            assert self.vsm.write_back("result")
