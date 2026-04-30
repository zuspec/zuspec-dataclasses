"""End-to-end and unit tests for zdc built-in constraint functions.

Covers three categories:

1. Constant-folding path (bound values) — ``sext``, ``cbit``, ``signed``
2. Variable-operand path — same functions with ``zdc.rand()`` operands
3. Boolean MUX semantics — 1-bit selector sign-extension in ``&`` / ``|``
4. Propagator unit tests — direct propagator API

All action classes are defined at module level so that ``inspect.getsource()``
can retrieve their source when the constraint compiler processes them.
"""

import dataclasses
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.solver.api import randomize, RandomizationError


# ---------------------------------------------------------------------------
# Shared dummy component
# ---------------------------------------------------------------------------

class DummyComp(zdc.Component):
    pass


# ---------------------------------------------------------------------------
# Bound-value helpers (plain dataclasses used as flow-input stand-ins)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class BoundInt:
    """Carries a single integer bound value (non-rand, walks public attrs)."""
    val: int = 0


@dataclasses.dataclass
class BoundPair:
    """Carries two integer bound values."""
    a: int = 0
    b: int = 0


# ---------------------------------------------------------------------------
# Action classes — Constant-folding path
# ---------------------------------------------------------------------------

@zdc.dataclass
class SextBoundAction(zdc.Action[DummyComp]):
    """result == sext(inp.val, 5) — all operands from bound non-rand field."""
    inp: BoundInt = dataclasses.field(default_factory=BoundInt)
    result: zdc.i32 = zdc.rand()

    @zdc.constraint
    def c_sext(self):
        assert self.result == zdc.sext(self.inp.val, 5)


@zdc.dataclass
class SextBound12Action(zdc.Action[DummyComp]):
    """result == sext(inp.val, 12) — 12-bit immediate sign extension."""
    inp: BoundInt = dataclasses.field(default_factory=BoundInt)
    result: zdc.i32 = zdc.rand()

    @zdc.constraint
    def c_sext(self):
        assert self.result == zdc.sext(self.inp.val, 12)


@zdc.dataclass
class CbitBoundAction(zdc.Action[DummyComp]):
    """flag == cbit(inp.a > inp.b) — all operands bound."""
    inp: BoundPair = dataclasses.field(default_factory=BoundPair)
    flag: zdc.u1 = zdc.rand()

    @zdc.constraint
    def c_cbit(self):
        assert self.flag == zdc.cbit(self.inp.a > self.inp.b)


@zdc.dataclass
class SignedBoundAction(zdc.Action[DummyComp]):
    """flag == cbit(signed(inp.val) < 0) — tests signed reinterpretation."""
    inp: BoundInt = dataclasses.field(default_factory=BoundInt)
    flag: zdc.u1 = zdc.rand()

    @zdc.constraint
    def c_signed(self):
        assert self.flag == zdc.cbit(zdc.signed(self.inp.val) < 0)


# ---------------------------------------------------------------------------
# Action classes — Variable-operand path
# ---------------------------------------------------------------------------

@zdc.dataclass
class SextVarAction(zdc.Action[DummyComp]):
    """result == sext(src, 5) — both fields are rand; sext constrains domain."""
    src: zdc.u5 = zdc.rand()    # 5-bit unsigned [0, 31]
    result: zdc.i32 = zdc.rand()

    @zdc.constraint
    def c_sext(self):
        assert self.result == zdc.sext(self.src, 5)


@zdc.dataclass
class CbitVarAction(zdc.Action[DummyComp]):
    """flag == cbit(x > 10) — cbit applied to a comparison of a rand field."""
    x: zdc.u32 = zdc.field(rand=True, domain=(0, 20))
    flag: zdc.u1 = zdc.rand()

    @zdc.constraint
    def c_cbit(self):
        assert self.flag == zdc.cbit(self.x > 10)


@zdc.dataclass
class SignedVarAction(zdc.Action[DummyComp]):
    """flag == cbit(signed(val) < 0) — signed view of a rand u32 field.

    Domain is narrowed to [0x7FFF_FF00, 0x8000_00FF] to exercise the
    sign boundary without exhausting the full 2^32 space.
    """
    val: zdc.u32 = zdc.field(rand=True, domain=(0x7FFF_FF00, 0x8000_00FF))
    flag: zdc.u1 = zdc.rand()

    @zdc.constraint
    def c_signed(self):
        assert self.flag == zdc.cbit(zdc.signed(self.val) < 0)


# ---------------------------------------------------------------------------
# Action classes — Boolean MUX semantics
# ---------------------------------------------------------------------------

@zdc.dataclass
class MuxSelectAction(zdc.Action[DummyComp]):
    """Tests 1-bit selector & 32-bit data MUX pattern.

    result == ((sel == 1) & data_a) | ((sel == 0) & data_b)
    All fields from bound inp; result is rand.
    """
    inp: BoundPair = dataclasses.field(default_factory=BoundPair)  # inp.a=sel, inp.b=data
    result: zdc.u32 = zdc.rand()

    @zdc.constraint
    def c_mux(self):
        assert self.result == (
            ((self.inp.a == 1) & self.inp.b) |
            ((self.inp.a == 0) & 0)
        )


@zdc.dataclass
class SltMuxAction(zdc.Action[DummyComp]):
    """Tests the SLT MUX pattern: cond_reg & cond_funct & cbit(signed_cmp).

    Mirrors the actual execute.py pattern:
        result == (opcode == OP_REG) & (funct3 == 2)
                  & cbit(signed(rs1) < signed(rs2))
    All operands from bound inp.
    """
    inp: BoundInt = dataclasses.field(default_factory=BoundInt)  # inp.val = opcode
    inp2: BoundInt = dataclasses.field(default_factory=BoundInt)  # inp2.val = rs1_val
    inp3: BoundInt = dataclasses.field(default_factory=BoundInt)  # inp3.val = rs2_val
    result: zdc.u32 = zdc.rand()

    @zdc.constraint
    def c_slt(self):
        assert self.result == (
            ((self.inp.val == 0x33) & (0 == 0))   # opcode==OP_REG always matches in test
            & zdc.cbit(zdc.signed(self.inp2.val) < zdc.signed(self.inp3.val))
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make(cls, **kwargs):
    """Instantiate an action with default field values, then apply kwargs."""
    obj = object.__new__(cls)
    for f in dataclasses.fields(cls):
        if f.default is not dataclasses.MISSING:
            object.__setattr__(obj, f.name, f.default)
        elif f.default_factory is not dataclasses.MISSING:
            object.__setattr__(obj, f.name, f.default_factory())
        else:
            object.__setattr__(obj, f.name, None)
    for k, v in kwargs.items():
        object.__setattr__(obj, k, v)
    return obj


# ---------------------------------------------------------------------------
# Tests: constant-folding path
# ---------------------------------------------------------------------------

class TestSextConstantFold:
    """zdc.sext() with all operands pre-bound (constant-fold path)."""

    def test_positive_no_sign_extension(self):
        """sext(0x0F, 5) → 15 (bit 4 = 0, no sign flip)."""
        action = _make(SextBoundAction, inp=BoundInt(val=0x0F))
        randomize(action)
        assert action.result == 15

    def test_negative_sign_extension(self):
        """sext(0b11011, 5) → 0b11011 = 27 → sign bit set → 27 - 32 = -5."""
        action = _make(SextBoundAction, inp=BoundInt(val=0b11011))
        randomize(action)
        assert action.result == -5

    def test_sign_bit_set_all_ones(self):
        """sext(0b11111, 5) → 31 → bit 4 = 1 → 31 - 32 = -1."""
        action = _make(SextBoundAction, inp=BoundInt(val=0b11111))
        randomize(action)
        assert action.result == -1

    def test_zero(self):
        """sext(0, 5) → 0."""
        action = _make(SextBoundAction, inp=BoundInt(val=0))
        randomize(action)
        assert action.result == 0

    def test_imm12_negative(self):
        """sext(0xFFF, 12) → -1 (12-bit all-ones sign-extends to -1)."""
        action = _make(SextBound12Action, inp=BoundInt(val=0xFFF))
        randomize(action)
        assert action.result == -1

    def test_imm12_positive(self):
        """sext(0x7FF, 12) → 2047 (positive, bit 11 = 0)."""
        action = _make(SextBound12Action, inp=BoundInt(val=0x7FF))
        randomize(action)
        assert action.result == 2047


class TestCbitConstantFold:
    """zdc.cbit() with all operands pre-bound (constant-fold path)."""

    def test_true(self):
        """cbit(5 > 3) → 1."""
        action = _make(CbitBoundAction, inp=BoundPair(a=5, b=3))
        randomize(action)
        assert action.flag == 1

    def test_false(self):
        """cbit(3 > 5) → 0."""
        action = _make(CbitBoundAction, inp=BoundPair(a=3, b=5))
        randomize(action)
        assert action.flag == 0

    def test_equal_is_false(self):
        """cbit(5 > 5) → 0."""
        action = _make(CbitBoundAction, inp=BoundPair(a=5, b=5))
        randomize(action)
        assert action.flag == 0


class TestSignedConstantFold:
    """zdc.signed() with all operands pre-bound (constant-fold path)."""

    def test_negative_u32(self):
        """signed(0xFFFFFFFF) < 0 → True → flag=1."""
        action = _make(SignedBoundAction, inp=BoundInt(val=0xFFFF_FFFF))
        randomize(action)
        assert action.flag == 1

    def test_positive_u32(self):
        """signed(1) < 0 → False → flag=0."""
        action = _make(SignedBoundAction, inp=BoundInt(val=1))
        randomize(action)
        assert action.flag == 0

    def test_min_negative(self):
        """signed(0x80000000) < 0 → True (min signed 32-bit) → flag=1."""
        action = _make(SignedBoundAction, inp=BoundInt(val=0x8000_0000))
        randomize(action)
        assert action.flag == 1

    def test_max_positive(self):
        """signed(0x7FFFFFFF) < 0 → False (max positive) → flag=0."""
        action = _make(SignedBoundAction, inp=BoundInt(val=0x7FFF_FFFF))
        randomize(action)
        assert action.flag == 0

    def test_zero(self):
        """signed(0) < 0 → False → flag=0."""
        action = _make(SignedBoundAction, inp=BoundInt(val=0))
        randomize(action)
        assert action.flag == 0


# ---------------------------------------------------------------------------
# Tests: variable-operand path
# ---------------------------------------------------------------------------

class TestSextVariable:
    """zdc.sext() with rand operands — solver must satisfy the constraint."""

    def test_correct_sign_extension(self):
        """For any randomized src (0-31), result == sext(src, 5)."""
        action = _make(SextVarAction)
        for _ in range(40):
            randomize(action)
            src = action.src
            expected = src - 32 if src >= 16 else src
            assert action.result == expected, (
                f"src={src}, expected={expected}, got result={action.result}"
            )

    def test_negative_results_possible(self):
        """Solver should occasionally produce negative results (src >= 16)."""
        action = _make(SextVarAction)
        negatives = 0
        for _ in range(100):
            randomize(action)
            if action.result < 0:
                negatives += 1
        assert negatives > 0, "Sign-extension never produced a negative result"

    def test_positive_results_possible(self):
        """Solver should occasionally produce positive results (src < 16)."""
        action = _make(SextVarAction)
        positives = 0
        for _ in range(100):
            randomize(action)
            if action.result >= 0:
                positives += 1
        assert positives > 0, "Sign-extension never produced a non-negative result"


class TestCbitVariable:
    """zdc.cbit() with rand operand — flag must mirror the comparison."""

    def test_flag_consistent_with_x(self):
        """flag == cbit(x > 10): flag=1 iff x > 10."""
        action = _make(CbitVarAction)
        for _ in range(50):
            randomize(action)
            expected = 1 if action.x > 10 else 0
            assert action.flag == expected, (
                f"x={action.x}, expected flag={expected}, got {action.flag}"
            )

    def test_both_flag_values_occur(self):
        """Solver should sometimes set flag=0 (x<=10) and sometimes flag=1 (x>10)."""
        action = _make(CbitVarAction)
        flags = {0, 1}
        seen = set()
        for _ in range(100):
            randomize(action)
            seen.add(action.flag)
        assert seen == flags, f"Only saw flag values {seen}, expected {{0, 1}}"


class TestSignedViewVariable:
    """zdc.signed() with rand operand — solver must respect sign interpretation."""

    def test_flag_consistent_with_val(self):
        """flag == cbit(signed(val) < 0): flag=1 iff val >= 0x80000000."""
        action = _make(SignedVarAction)
        for _ in range(40):
            randomize(action)
            expected = 1 if action.val >= 0x8000_0000 else 0
            assert action.flag == expected, (
                f"val=0x{action.val:08x}, expected flag={expected}, got {action.flag}"
            )


# ---------------------------------------------------------------------------
# Tests: Boolean MUX semantics
# ---------------------------------------------------------------------------

class TestBooleanMuxSemantics:
    """Verify that 1-bit selector & N-bit data produces the data value, not 1."""

    def test_selector_true_passes_data(self):
        """(sel==1) & data → data (not 1) when sel==1."""
        action = _make(MuxSelectAction, inp=BoundPair(a=1, b=0xABCD_1234))
        randomize(action)
        assert action.result == 0xABCD_1234, (
            f"selector=1 should pass data 0xABCD1234; got 0x{action.result:08x}"
        )

    def test_selector_false_produces_zero(self):
        """(sel==1) & data → 0 when sel==0."""
        action = _make(MuxSelectAction, inp=BoundPair(a=0, b=0xABCD_1234))
        randomize(action)
        assert action.result == 0, (
            f"selector=0 should block data; got 0x{action.result:08x}"
        )

    def test_slt_pattern_negative_result(self):
        """SLT-style pattern: signed(-1) < signed(1) → flag=1 → result=1."""
        action = _make(
            SltMuxAction,
            inp=BoundInt(val=0x33),      # opcode = OP_REG
            inp2=BoundInt(val=0xFFFF_FFFF),  # rs1 = -1 (signed)
            inp3=BoundInt(val=1),            # rs2 = 1
        )
        randomize(action)
        assert action.result == 1, (
            f"signed(-1) < signed(1) → cbit=1; expected result=1, got {action.result}"
        )

    def test_slt_pattern_positive_false(self):
        """SLT-style pattern: signed(5) < signed(3) → flag=0 → result=0."""
        action = _make(
            SltMuxAction,
            inp=BoundInt(val=0x33),
            inp2=BoundInt(val=5),
            inp3=BoundInt(val=3),
        )
        randomize(action)
        assert action.result == 0, (
            f"signed(5) < signed(3) is False; expected result=0, got {action.result}"
        )

    def test_chained_conditions_pass_data(self):
        """Chained: (a==1) & (b==0) & data should equal data, not 1."""
        # Use inp.a as two separate conditions both true, inp.b as data
        @zdc.dataclass
        class ChainedMux(zdc.Action[DummyComp]):
            inp: BoundPair = dataclasses.field(default_factory=BoundPair)
            result: zdc.u32 = zdc.rand()

            @zdc.constraint
            def c_chain(self):
                assert self.result == (
                    (self.inp.a == 1) & (self.inp.a == 1) & self.inp.b
                )

        action = _make(ChainedMux, inp=BoundPair(a=1, b=0xDEAD_BEEF))
        randomize(action)
        assert action.result == 0xDEAD_BEEF, (
            f"chained selectors both true should pass data; got 0x{action.result:08x}"
        )


# ---------------------------------------------------------------------------
# Tests: Propagator unit tests
# ---------------------------------------------------------------------------

class TestSextPropagator:
    """Direct unit tests for the SextPropagator."""

    def _make_vars(self, result_domain, value_domain, width=32):
        from zuspec.dataclasses.solver.core.variable import Variable
        from zuspec.dataclasses.solver.core.domain import IntDomain
        result = Variable("result", IntDomain(result_domain, width=width, signed=True))
        value = Variable("value", IntDomain(value_domain, width=width, signed=False))
        return result, value

    def test_forward_positive(self):
        """sext(7, 4) → 7 (positive, no sign flip)."""
        from zuspec.dataclasses.solver.propagators.functions import SextPropagator
        from zuspec.dataclasses.solver.core.variable import Variable
        from zuspec.dataclasses.solver.core.domain import IntDomain
        result = Variable("result", IntDomain([(-8, 7)], width=32, signed=True))
        value = Variable("value", IntDomain([(7, 7)], width=32, signed=False))
        prop = SextPropagator("result", "value", bits=4)
        prop.propagate({"result": result, "value": value})
        assert result.domain.is_singleton()
        assert result.domain.min_val == 7

    def test_forward_negative(self):
        """sext(15, 4) → -1 (all-ones 4-bit sign-extends to -1)."""
        from zuspec.dataclasses.solver.propagators.functions import SextPropagator
        from zuspec.dataclasses.solver.core.variable import Variable
        from zuspec.dataclasses.solver.core.domain import IntDomain
        result = Variable("result", IntDomain([(-8, 7)], width=32, signed=True))
        value = Variable("value", IntDomain([(15, 15)], width=32, signed=False))
        prop = SextPropagator("result", "value", bits=4)
        prop.propagate({"result": result, "value": value})
        assert result.domain.is_singleton()
        assert result.domain.min_val == -1

    def test_backward_constrain_source(self):
        """Backward: result==-1 with bits=4 → value must be 15."""
        from zuspec.dataclasses.solver.propagators.functions import SextPropagator
        from zuspec.dataclasses.solver.core.variable import Variable
        from zuspec.dataclasses.solver.core.domain import IntDomain
        result = Variable("result", IntDomain([(-1, -1)], width=32, signed=True))
        value = Variable("value", IntDomain([(0, 15)], width=32, signed=False))
        prop = SextPropagator("result", "value", bits=4)
        prop.propagate({"result": result, "value": value})
        assert value.domain.is_singleton()
        assert value.domain.min_val == 15


class TestCbitPropagator:
    """Direct unit tests for the CbitPropagator."""

    def test_forward_non_zero(self):
        """cbit(inner=5) → 1."""
        from zuspec.dataclasses.solver.propagators.functions import CbitPropagator
        from zuspec.dataclasses.solver.core.variable import Variable
        from zuspec.dataclasses.solver.core.domain import IntDomain
        result = Variable("result", IntDomain([(0, 1)], width=1, signed=False))
        inner = Variable("inner", IntDomain([(5, 5)], width=32, signed=False))
        prop = CbitPropagator("result", "inner")
        prop.propagate({"result": result, "inner": inner})
        assert result.domain.is_singleton()
        assert result.domain.min_val == 1

    def test_forward_zero(self):
        """cbit(inner=0) → 0."""
        from zuspec.dataclasses.solver.propagators.functions import CbitPropagator
        from zuspec.dataclasses.solver.core.variable import Variable
        from zuspec.dataclasses.solver.core.domain import IntDomain
        result = Variable("result", IntDomain([(0, 1)], width=1, signed=False))
        inner = Variable("inner", IntDomain([(0, 0)], width=32, signed=False))
        prop = CbitPropagator("result", "inner")
        prop.propagate({"result": result, "inner": inner})
        assert result.domain.is_singleton()
        assert result.domain.min_val == 0

    def test_backward_result_one_excludes_zero(self):
        """Backward: result=1 → inner domain must exclude 0."""
        from zuspec.dataclasses.solver.propagators.functions import CbitPropagator
        from zuspec.dataclasses.solver.core.variable import Variable
        from zuspec.dataclasses.solver.core.domain import IntDomain
        result = Variable("result", IntDomain([(1, 1)], width=1, signed=False))
        inner = Variable("inner", IntDomain([(0, 10)], width=32, signed=False))
        prop = CbitPropagator("result", "inner")
        prop.propagate({"result": result, "inner": inner})
        assert inner.domain.min_val > 0, "result=1 means inner cannot be 0"


class TestSignedViewPropagator:
    """Direct unit tests for the SignedViewPropagator."""

    def test_forward_unsigned_to_signed(self):
        """Forward: inner=0xFFFFFFFF (unsigned) → result=-1 (signed 32-bit)."""
        from zuspec.dataclasses.solver.propagators.functions import SignedViewPropagator
        from zuspec.dataclasses.solver.core.variable import Variable
        from zuspec.dataclasses.solver.core.domain import IntDomain
        result = Variable("result", IntDomain([(-2**31, 2**31 - 1)], width=32, signed=True))
        inner = Variable("inner", IntDomain([(0xFFFF_FFFF, 0xFFFF_FFFF)], width=32, signed=False))
        prop = SignedViewPropagator("result", "inner", width=32)
        prop.propagate({"result": result, "inner": inner})
        assert result.domain.is_singleton()
        assert result.domain.min_val == -1

    def test_forward_positive_unchanged(self):
        """Forward: inner=42 → result=42 (no sign flip needed)."""
        from zuspec.dataclasses.solver.propagators.functions import SignedViewPropagator
        from zuspec.dataclasses.solver.core.variable import Variable
        from zuspec.dataclasses.solver.core.domain import IntDomain
        result = Variable("result", IntDomain([(-2**31, 2**31 - 1)], width=32, signed=True))
        inner = Variable("inner", IntDomain([(42, 42)], width=32, signed=False))
        prop = SignedViewPropagator("result", "inner", width=32)
        prop.propagate({"result": result, "inner": inner})
        assert result.domain.is_singleton()
        assert result.domain.min_val == 42
