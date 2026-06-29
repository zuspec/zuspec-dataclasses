"""Integration test: output buffer .t write via @zdc.constraint.

Tests that ``assert self.out.t.field == expr`` inside a constraint body
correctly writes solved values into the output buffer's payload.

Classes must be at module level for inspect.getsource() to work.
"""
import dataclasses
import pytest
import zuspec.dataclasses as zdc
from zuspec.be.py.solver.api import randomize, RandomizationError


# ---------------------------------------------------------------------------
# Payload dataclasses
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class SimpleOut:
    result: zdc.u32 = zdc.field(rand=True, domain=(0, 0xFFFFFFFF))
    flag: zdc.u1 = zdc.field(rand=True, domain=(0, 1))


@dataclasses.dataclass
class TwoFieldOut:
    a: zdc.u8 = zdc.field(rand=True, domain=(0, 255))
    b: zdc.u8 = zdc.field(rand=True, domain=(0, 255))


# ---------------------------------------------------------------------------
# Actions under test (module-level so getsource() works)
# ---------------------------------------------------------------------------

class TestComp(zdc.Component):
    pass


@zdc.dataclass
class ConstantOutputAction(zdc.Action[TestComp]):
    """Constraint forces out.t.result to a fixed value."""
    out: zdc.Buffer[SimpleOut] = zdc.output()

    @zdc.constraint
    def c_result(self):
        assert self.out.t.result == 42
        assert self.out.t.flag == 1


@zdc.dataclass
class WitnessOutputAction(zdc.Action[TestComp]):
    """Witness variable forwarded to output buffer field."""
    inp_val: zdc.u8 = zdc.rand()
    out: zdc.Buffer[TwoFieldOut] = zdc.output()

    @zdc.constraint
    def c_out(self):
        # Witness: intermediate value
        doubled: zdc.u8 = zdc.rand()
        assert doubled == (self.inp_val * 2) & 0xFF
        assert self.out.t.a == doubled
        assert self.out.t.b == self.inp_val


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOutputBufferWrite:
    """End-to-end tests for output buffer .t constraint writes."""

    def test_constant_output_result(self):
        """out.t.result is constrained to 42 and flag to 1."""
        action = ConstantOutputAction(comp=TestComp())
        randomize(action)
        out_t = action.out.t  # proxy.t -> payload
        assert out_t.result == 42, f"Expected result=42, got {out_t.result}"
        assert out_t.flag == 1, f"Expected flag=1, got {out_t.flag}"

    def test_witness_forwarded_to_output(self):
        """Witness variable correctly forwarded to out.t.a and out.t.b."""
        action = WitnessOutputAction(comp=TestComp())
        randomize(action)
        out_t = action.out.t
        inp = action.inp_val
        # Constraint: doubled == (inp_val * 2) & 0xFF; out.a == doubled; out.b == inp_val
        assert out_t.a == (inp * 2) & 0xFF, (
            f"Expected a={(inp * 2) & 0xFF}, got {out_t.a} (inp_val={inp})"
        )
        assert out_t.b == inp, f"Expected b={inp}, got {out_t.b}"
