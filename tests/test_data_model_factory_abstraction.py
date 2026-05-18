"""Phase 2 tests — DataModelFactory abstraction-field hook.

Verifies that Counter/ModuloCounter/WatchdogCounter fields are intercepted by
the abstraction hook and produce ``AbstractionFieldIR`` nodes rather than going
through the generic ``DataTypeComponent`` path.
"""
from __future__ import annotations

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.data_model_factory import DataModelFactory
from zuspec.ir.core.abstraction_field_ir import AbstractionFieldIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build(cls):
    """Run DataModelFactory on *cls* and return the ComponentIR-like object."""
    factory = DataModelFactory()
    ctx = factory.build([cls])
    # The IR for *cls* is keyed by its __name__ in ctx.type_m
    return ctx.type_m.get(cls.__name__) or list(ctx.type_m.values())[-1]


# ---------------------------------------------------------------------------
# Counter field interception
# ---------------------------------------------------------------------------

def test_counter_field_not_elaborated_as_component():
    """Counter field must NOT appear as a DataTypeComponent in the type map."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        cnt: zdc.Counter = zdc.inst(zdc.Counter, kwargs={"WIDTH": 8})

    factory = DataModelFactory()
    ctx = factory.build([MyComp])
    # Counter must NOT have been added to pending / type_m as a component
    type_names = list(ctx.type_m.keys())
    assert "Counter" not in type_names, (
        f"Counter should not be in type_m, got: {type_names}"
    )


def test_counter_field_produces_abstraction_field_ir():
    """The field at the counter position must be an ``AbstractionFieldIR``."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        cnt: zdc.Counter = zdc.inst(zdc.Counter, kwargs={"WIDTH": 8})

    ir = _build(MyComp)
    abstraction_fields = [f for f in ir.fields if isinstance(f, AbstractionFieldIR)]
    assert len(abstraction_fields) == 1
    af = abstraction_fields[0]
    assert af.spec_type_name == "Counter"
    assert af.field_name == "cnt"


def test_counter_field_ir_has_correct_kwargs():
    """``inst_kwargs`` on the ``AbstractionFieldIR`` must match the zdc.inst() call."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        cnt: zdc.Counter = zdc.inst(zdc.Counter, kwargs={"WIDTH": 16})

    ir = _build(MyComp)
    af = next(f for f in ir.fields if isinstance(f, AbstractionFieldIR))
    assert af.inst_kwargs.get("WIDTH") == 16


def test_non_counter_field_still_uses_generic_path():
    """Plain ``u32`` fields must still produce ordinary ``Field`` IR nodes."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        value: zdc.u32 = zdc.field(default=0)

    ir = _build(MyComp)
    abstraction_fields = [f for f in ir.fields if isinstance(f, AbstractionFieldIR)]
    assert abstraction_fields == [], (
        f"No abstraction fields expected for plain u32 field, got: {abstraction_fields}"
    )


def test_counter_field_index_correct():
    """``field_index`` on the ``AbstractionFieldIR`` must match the insertion order."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        value: zdc.u32 = zdc.field(default=0)
        cnt: zdc.Counter = zdc.inst(zdc.Counter, kwargs={"WIDTH": 8})

    ir = _build(MyComp)
    af = next(f for f in ir.fields if isinstance(f, AbstractionFieldIR))
    # Counter is the SECOND field, so index should be 1
    assert af.field_index == 1


def test_modulo_counter_field_produces_abstraction_ir():
    """``ModuloCounter`` field must also be intercepted."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        baud: zdc.ModuloCounter = zdc.inst(zdc.ModuloCounter, kwargs={"PERIOD": 868})

    ir = _build(MyComp)
    abstraction_fields = [f for f in ir.fields if isinstance(f, AbstractionFieldIR)]
    assert len(abstraction_fields) == 1
    af = abstraction_fields[0]
    assert af.spec_type_name == "ModuloCounter"
    assert af.inst_kwargs.get("PERIOD") == 868


def test_watchdog_counter_field_produces_abstraction_ir():
    """``WatchdogCounter`` field must also be intercepted."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        wdog: zdc.WatchdogCounter = zdc.inst(zdc.WatchdogCounter, kwargs={"TIMEOUT": 500})

    ir = _build(MyComp)
    abstraction_fields = [f for f in ir.fields if isinstance(f, AbstractionFieldIR)]
    assert len(abstraction_fields) == 1
    af = abstraction_fields[0]
    assert af.spec_type_name == "WatchdogCounter"
    assert af.inst_kwargs.get("TIMEOUT") == 500
