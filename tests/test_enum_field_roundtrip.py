"""Tests for @zdc.enum field capture in DataModelFactory (Phase 0.2).

Verifies that a @zdc.enum-decorated class used as a field type is captured
as DataTypeEnum by DataModelFactory, closing the Python round-trip.
"""
from __future__ import annotations

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.data_model_factory import DataModelFactory


# ---------------------------------------------------------------------------
# Helper: resolve a field type from a built component IR
# ---------------------------------------------------------------------------

def _get_field_type(component_cls, field_name: str):
    ctx = DataModelFactory().build(component_cls)
    comp_ir = ctx.type_m.get(
        getattr(component_cls, "__qualname__", None)
    ) or ctx.type_m.get(component_cls.__name__)
    assert comp_ir is not None, f"Could not find IR for {component_cls.__name__}"
    for f in comp_ir.fields:
        if f.name == field_name:
            return f.datatype
    raise KeyError(f"Field {field_name!r} not found in {component_cls.__name__}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestZdcEnumCapturedAsDataTypeEnum:
    def test_zdc_enum_captured_as_DataTypeEnum(self):
        """@zdc.enum field is resolved to DataTypeEnum, not DataTypeRef."""
        @zdc.enum
        class State:
            IDLE = 0
            WAIT = 1

        @zdc.dataclass
        class _Comp(zdc.SyncComponent):
            _state: State = zdc.field(width=1)

        dt = _get_field_type(_Comp, "_state")
        assert type(dt).__name__ == "DataTypeEnum", (
            f"Expected DataTypeEnum, got {type(dt).__name__}"
        )

    def test_zdc_enum_items_correct(self):
        """DataTypeEnum items dict matches the decorated class members."""
        @zdc.enum
        class Color:
            RED   = 0
            GREEN = 1
            BLUE  = 2

        @zdc.dataclass
        class _Comp(zdc.SyncComponent):
            _color: Color = zdc.field(width=2)

        dt = _get_field_type(_Comp, "_color")
        assert type(dt).__name__ == "DataTypeEnum"
        assert dt.items == {"RED": 0, "GREEN": 1, "BLUE": 2}

    def test_intEnum_still_works(self):
        """Existing IntEnum path is not broken by the new check."""
        import enum as _enum

        class OldStyle(_enum.IntEnum):
            A = 0
            B = 1

        @zdc.dataclass
        class _Comp(zdc.SyncComponent):
            _v: OldStyle = zdc.field(width=1)

        dt = _get_field_type(_Comp, "_v")
        assert type(dt).__name__ == "DataTypeEnum"

    def test_enum_round_trip_synthesizable(self):
        """Component with @zdc.enum-typed state register synthesizes without error."""
        from zuspec.synth import synthesize

        @zdc.enum
        class FSMState:
            IDLE = 0
            RUN  = 1

        @zdc.dataclass
        class _EnumComp(zdc.SyncComponent):
            _state: FSMState = zdc.field(width=1)

            @zdc.sync
            def _fsm(self):
                pass  # minimal body — just check it doesn't crash

        sv = synthesize(_EnumComp)
        assert sv is not None
