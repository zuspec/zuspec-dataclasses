"""Integration tests for deterministic constraint evaluation.

These tests exercise the full pipeline:
  DataModelFactory → build_from_struct → ConstraintAnalyser → PythonFunctionEmitter → solve

Classes MUST be at module level so DataModelFactory's inspect.getsource() works.
"""
import dataclasses
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.solver.deterministic import (
    build_from_struct, ConstraintAnalyser, PythonFunctionEmitter,
)
from zuspec.dataclasses.solver.deterministic.exceptions import PreconditionViolation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_struct(cls, comp_cls=None):
    from zuspec.dataclasses.data_model_factory import DataModelFactory
    classes = [comp_cls, cls] if comp_cls is not None else [cls]
    ctx = DataModelFactory().build(classes)
    name = cls.__qualname__
    st = ctx.type_m.get(name) or ctx.type_m.get(cls.__name__)
    assert st is not None, f"IR struct for {cls.__name__} not found"
    return st


def _compile(cls, comp_cls=None):
    """Return a compiled solve function for *cls*."""
    st = _get_struct(cls, comp_cls)
    vsm = build_from_struct(st, py_class=cls)
    analyser = ConstraintAnalyser()
    plan = analyser.analyse(cls, st, vsm)
    if plan.underdetermined:
        raise RuntimeError(f"Underdetermined: {plan.underdetermined}")
    return PythonFunctionEmitter().emit(plan), plan


class _Comp(zdc.Component):
    pass


# ---------------------------------------------------------------------------
# Scenario 1: Simple decode – output = f(input)
#   decode_result = (instr >> 7) & 0x1F
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class DecodeRdAction(zdc.Action[_Comp]):
    instr: zdc.u32 = zdc.flow_input(default=0)
    rd: zdc.u32 = zdc.flow_output(default=0)

    @zdc.constraint
    def decode_rd(self):
        self.rd == (self.instr >> 7) & 0x1F


class TestDecodeRd:
    def setup_method(self):
        self.fn, self.plan = _compile(DecodeRdAction, _Comp)

    def test_plan_has_no_underdetermined(self):
        assert not self.plan.underdetermined

    def test_plan_has_assignment_for_rd(self):
        names = [a.var_name for a in self.plan.assignments]
        assert "rd" in names

    def test_rd_assignment_write_back(self):
        for a in self.plan.assignments:
            if a.var_name == "rd":
                assert a.write_back

    def test_solve_extracts_rd_bits(self):
        obj = DecodeRdAction.__new__(DecodeRdAction)
        obj.instr = 0b_0000_0000_0000_0000_0000_01111_0000000  # rd = 0b01111 = 15
        obj.rd = 0
        self.fn(obj)
        assert obj.rd == 15

    def test_solve_zero_instr(self):
        obj = DecodeRdAction.__new__(DecodeRdAction)
        obj.instr = 0
        obj.rd = 0xFF
        self.fn(obj)
        assert obj.rd == 0

    def test_solve_max_rd(self):
        obj = DecodeRdAction.__new__(DecodeRdAction)
        obj.instr = 0b_0000_0000_0000_0000_0000_11111_0000000  # rd = 31
        obj.rd = 0
        self.fn(obj)
        assert obj.rd == 31

    @pytest.mark.parametrize("instr,expected_rd", [
        (0x00000000, 0),
        (0x00000080, 1),    # bit 7 set → rd=1
        (0x00000F80, 0x1F), # bits 11:7 = 0x1F → rd=31
        (0xFFFFFFFF, 0x1F),
    ])
    def test_parametric_decode(self, instr, expected_rd):
        obj = DecodeRdAction.__new__(DecodeRdAction)
        obj.instr = instr
        obj.rd = 0
        self.fn(obj)
        assert obj.rd == expected_rd, f"instr=0x{instr:08X}: expected rd={expected_rd}, got {obj.rd}"


# ---------------------------------------------------------------------------
# Scenario 2: Multi-field decode
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class MultiDecodeAction(zdc.Action[_Comp]):
    instr: zdc.u32 = zdc.flow_input(default=0)
    rd: zdc.u32 = zdc.flow_output(default=0)
    rs1: zdc.u32 = zdc.flow_output(default=0)
    rs2: zdc.u32 = zdc.flow_output(default=0)
    opcode: zdc.u32 = zdc.flow_output(default=0)

    @zdc.constraint
    def decode_fields(self):
        self.rd     == (self.instr >> 7)  & 0x1F
        self.rs1    == (self.instr >> 15) & 0x1F
        self.rs2    == (self.instr >> 20) & 0x1F
        self.opcode == self.instr & 0x7F


class TestMultiDecode:
    def setup_method(self):
        self.fn, self.plan = _compile(MultiDecodeAction, _Comp)

    def test_no_underdetermined(self):
        assert not self.plan.underdetermined

    def test_all_outputs_assigned(self):
        names = {a.var_name for a in self.plan.assignments}
        assert {"rd", "rs1", "rs2", "opcode"}.issubset(names)

    def test_decode_r_type(self):
        # ADD x1, x2, x3 = 0x00310133
        # opcode=0x33, rd=2, rs1=2, rs2=3 -- just check the decode is consistent
        instr = 0x00310133
        obj = MultiDecodeAction.__new__(MultiDecodeAction)
        obj.instr = instr
        for f in ("rd", "rs1", "rs2", "opcode"):
            setattr(obj, f, 0)
        self.fn(obj)
        assert obj.opcode == (instr & 0x7F)
        assert obj.rd     == ((instr >> 7)  & 0x1F)
        assert obj.rs1    == ((instr >> 15) & 0x1F)
        assert obj.rs2    == ((instr >> 20) & 0x1F)


# ---------------------------------------------------------------------------
# Scenario 3: Constraint with precondition check (postcondition / assert)
#   opcode must be a known RV32I opcode (simple assert)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class DecodePcAction(zdc.Action[_Comp]):
    instr: zdc.u32 = zdc.flow_input(default=0)
    opcode: zdc.u32 = zdc.flow_output(default=0)

    @zdc.constraint
    def decode_opcode(self):
        self.opcode == self.instr & 0x7F

    @zdc.constraint
    def assert_opcode_lsbs(self):
        assert (self.instr & 0x3) == 0x3


class TestDecodeWithAssert:
    def setup_method(self):
        self.fn, self.plan = _compile(DecodePcAction, _Comp)

    def test_no_underdetermined(self):
        assert not self.plan.underdetermined

    def test_solve_normal(self):
        obj = DecodePcAction.__new__(DecodePcAction)
        obj.instr = 0x13  # opcode = 0x13, lsbs = 0x3 ✓
        obj.opcode = 0
        self.fn(obj)
        assert obj.opcode == 0x13


# ---------------------------------------------------------------------------
# Scenario 4: Purely rand (underdetermined) — analyser should detect this
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class UnderdeterminedAction(zdc.Action[_Comp]):
    x: zdc.u32 = zdc.field(rand=True, domain=(0, 255))
    y: zdc.u32 = zdc.field(rand=True, domain=(0, 255))

    @zdc.constraint
    def some_constraint(self):
        self.x + self.y == 100


class TestUnderdetermined:
    def test_plan_has_underdetermined(self):
        st = _get_struct(UnderdeterminedAction, _Comp)
        vsm = build_from_struct(st, py_class=UnderdeterminedAction)
        analyser = ConstraintAnalyser()
        plan = analyser.analyse(UnderdeterminedAction, st, vsm)
        # Both x and y are rand — at least one should be underdetermined
        # (cannot invert a 2-variable equation for both simultaneously)
        assert len(plan.underdetermined) > 0


# ---------------------------------------------------------------------------
# Scenario 5: Compiled solve is idempotent
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_same_input_same_output(self):
        fn, _ = _compile(DecodeRdAction, _Comp)
        results = set()
        obj = DecodeRdAction.__new__(DecodeRdAction)
        obj.instr = 0x00000F80
        for _ in range(5):
            obj.rd = 0
            fn(obj)
            results.add(obj.rd)
        assert results == {0x1F}


# ---------------------------------------------------------------------------
# Scenario 6: Verify fast path activates via randomize_bound_cached
# ---------------------------------------------------------------------------

class TestFastPathIntegration:
    def test_zdc_compiled_solve_is_set(self):
        """After first randomize_bound_cached(), the fast path should be cached on the class."""
        from zuspec.dataclasses.solver._core_solve import (
            randomize_bound_cached,
        )
        # Ensure _zdc_struct is populated on the class (via explicit build)
        # and clear any prior compiled-solve state for isolation
        st = _get_struct(DecodeRdAction, _Comp)
        DecodeRdAction._zdc_struct = st
        if hasattr(DecodeRdAction, '_zdc_compiled_solve'):
            delattr(DecodeRdAction, '_zdc_compiled_solve')
        # Remove from analysis-done set so the first call triggers analysis
        from zuspec.dataclasses.solver._core_solve import _DETERMINISTIC_ANALYSIS_DONE
        _DETERMINISTIC_ANALYSIS_DONE.discard(DecodeRdAction)

        obj = DecodeRdAction.__new__(DecodeRdAction)
        obj.instr = 0x00000F80
        obj.rd = 0

        randomize_bound_cached(obj, st, seed=None, timeout_ms=None)

        assert hasattr(DecodeRdAction, '_zdc_compiled_solve'), (
            "_zdc_compiled_solve should be set after first randomize_bound_cached call"
        )
        assert obj.rd == 0x1F
