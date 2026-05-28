"""Phase 4 tests — Queue lowering-interface implementations.

Tests cover protocol membership, elaborate_field, SV generation, SVA
generation, deprecation of the ``queue()`` factory, and DataModelFactory
hook integration.
"""
from __future__ import annotations

import warnings
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.queue_type import Queue, _QueueAlias, _extract_elem_width
from zuspec.dataclasses.types import u32, u8
from zuspec.ir.core.interfaces import (
    Lowerable,
    ElaboratableInterface,
    SVEmittableInterface,
    SVAEmittableInterface,
    CSimEmittableInterface,
)
from zuspec.ir.core.abstraction_field_ir import AbstractionFieldIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_queue_ir(field_name='req_q', depth=8, elem_width=32, element_type=None):
    if element_type is None:
        element_type = u32
    return Queue.elaborate_field(
        field_name=field_name,
        field_index=0,
        inst_kwargs={'DEPTH': depth},
        element_type=element_type,
    )


# ---------------------------------------------------------------------------
# Protocol membership
# ---------------------------------------------------------------------------

class TestQueueProtocols:
    def test_queue_is_lowerable(self):
        assert Lowerable in Queue.__mro__

    def test_queue_is_elaboratable(self):
        assert ElaboratableInterface in Queue.__mro__

    def test_queue_is_sv_emittable(self):
        assert SVEmittableInterface in Queue.__mro__

    def test_queue_is_sva_emittable(self):
        assert SVAEmittableInterface in Queue.__mro__

    def test_queue_is_csim_emittable(self):
        assert CSimEmittableInterface in Queue.__mro__


# ---------------------------------------------------------------------------
# _QueueAlias unwrapping
# ---------------------------------------------------------------------------

class TestQueueAlias:
    def test_subscript_returns_alias(self):
        alias = Queue[u32]
        assert isinstance(alias, _QueueAlias)

    def test_alias_origin_is_queue(self):
        alias = Queue[u32]
        assert alias._origin is Queue

    def test_alias_item_is_u32(self):
        alias = Queue[u32]
        assert alias._item is u32

    def test_alias_repr(self):
        alias = Queue[u32]
        assert 'Queue' in repr(alias)


# ---------------------------------------------------------------------------
# _extract_elem_width helper
# ---------------------------------------------------------------------------

class TestExtractElemWidth:
    def test_u32_gives_32(self):
        assert _extract_elem_width(u32) == 32

    def test_u8_gives_8(self):
        assert _extract_elem_width(u8) == 8

    def test_none_gives_default(self):
        assert _extract_elem_width(None) == 32

    def test_unknown_type_gives_default(self):
        assert _extract_elem_width(int, default=16) == 16


# ---------------------------------------------------------------------------
# elaborate_field
# ---------------------------------------------------------------------------

class TestQueueElaborateField:
    def test_returns_abstraction_field_ir(self):
        ir = _make_queue_ir()
        assert isinstance(ir, AbstractionFieldIR)

    def test_is_abstraction_field(self):
        ir = _make_queue_ir()
        assert ir.is_abstraction_field is True

    def test_field_name_stored(self):
        ir = _make_queue_ir(field_name='my_q')
        assert ir.field_name == 'my_q'
        assert ir.name == 'my_q'

    def test_spec_type_name(self):
        ir = _make_queue_ir()
        assert ir.spec_type_name == 'Queue'

    def test_py_cls_is_queue(self):
        ir = _make_queue_ir()
        assert ir.py_cls is Queue

    def test_depth_from_inst_kwargs(self):
        ir = _make_queue_ir(depth=16)
        assert ir.ir_node['depth'] == 16

    def test_default_depth(self):
        ir = Queue.elaborate_field(
            field_name='q', field_index=0, inst_kwargs={}, element_type=u32)
        assert ir.ir_node['depth'] == 8

    def test_elem_width_from_element_type(self):
        ir = _make_queue_ir(element_type=u32)
        assert ir.ir_node['elem_width'] == 32

    def test_element_type_stored_in_ir_node(self):
        ir = _make_queue_ir(element_type=u32)
        assert ir.ir_node['element_type'] is u32


# ---------------------------------------------------------------------------
# sv_module_text
# ---------------------------------------------------------------------------

class TestQueueSVModule:
    def test_sv_contains_module(self):
        ir = _make_queue_ir()
        sv = Queue.sv_module_text(ir)
        assert 'module' in sv

    def test_sv_contains_endmodule(self):
        ir = _make_queue_ir()
        sv = Queue.sv_module_text(ir)
        assert 'endmodule' in sv

    def test_sv_contains_field_name(self):
        ir = _make_queue_ir(field_name='req_q')
        sv = Queue.sv_module_text(ir)
        assert 'req_q' in sv

    def test_sv_contains_fifo_ports(self):
        ir = _make_queue_ir()
        sv = Queue.sv_module_text(ir)
        assert 'wr_en' in sv
        assert 'rd_en' in sv

    def test_sv_depth_in_comment(self):
        ir = _make_queue_ir(depth=4)
        sv = Queue.sv_module_text(ir)
        assert '4' in sv


# ---------------------------------------------------------------------------
# sv_instance_text
# ---------------------------------------------------------------------------

class TestQueueSVInstance:
    def test_instance_contains_field_name(self):
        ir = _make_queue_ir(field_name='req_q')
        txt = Queue.sv_instance_text(ir)
        assert 'req_q' in txt

    def test_instance_contains_clk(self):
        ir = _make_queue_ir()
        txt = Queue.sv_instance_text(ir)
        assert 'clk' in txt

    def test_instance_contains_wr_en(self):
        ir = _make_queue_ir()
        txt = Queue.sv_instance_text(ir)
        assert 'wr_en' in txt

    def test_instance_contains_rd_en(self):
        ir = _make_queue_ir()
        txt = Queue.sv_instance_text(ir)
        assert 'rd_en' in txt


# ---------------------------------------------------------------------------
# rewrite_proc_stmts
# ---------------------------------------------------------------------------

class TestQueueRewriteProc:
    def test_rewrite_is_passthrough(self):
        ir = _make_queue_ir()
        stmts = ['s1', 's2', 's3']
        result = Queue.rewrite_proc_stmts(stmts, ir)
        assert result == stmts

    def test_rewrite_returns_list(self):
        ir = _make_queue_ir()
        result = Queue.rewrite_proc_stmts([], ir)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# sva_assert_properties / sva_assume_properties
# ---------------------------------------------------------------------------

class TestQueueSVA:
    def test_sva_generates_overflow_property(self):
        ir = _make_queue_ir(field_name='req_q')
        props = Queue.sva_assert_properties(ir)
        assert any('overflow' in p for p in props)

    def test_sva_generates_underflow_property(self):
        ir = _make_queue_ir(field_name='req_q')
        props = Queue.sva_assert_properties(ir)
        assert any('underflow' in p for p in props)

    def test_sva_contains_field_name(self):
        ir = _make_queue_ir(field_name='req_q')
        props = Queue.sva_assert_properties(ir)
        combined = '\n'.join(props)
        assert 'req_q' in combined

    def test_sva_assume_empty(self):
        ir = _make_queue_ir()
        assert Queue.sva_assume_properties(ir) == []

    def test_bmc_depth_at_least_1(self):
        ir = _make_queue_ir(depth=4)
        assert Queue.bmc_depth(ir) >= 1

    def test_bmc_depth_grows_with_queue_depth(self):
        ir4 = _make_queue_ir(depth=4)
        ir8 = _make_queue_ir(depth=8)
        assert Queue.bmc_depth(ir8) >= Queue.bmc_depth(ir4)

    def test_cutpoint_signals_empty(self):
        ir = _make_queue_ir()
        assert Queue.cutpoint_signals(ir) == []


# ---------------------------------------------------------------------------
# c_header / c_impl
# ---------------------------------------------------------------------------

class TestQueueCGen:
    def test_c_header_has_include_guard(self):
        ir = _make_queue_ir(field_name='req_q')
        h = Queue.c_header(ir)
        assert '#ifndef' in h and '#define' in h and '#endif' in h

    def test_c_header_contains_field_name(self):
        ir = _make_queue_ir(field_name='req_q')
        h = Queue.c_header(ir)
        assert 'req_q' in h

    def test_c_impl_contains_field_name(self):
        ir = _make_queue_ir(field_name='req_q')
        impl = Queue.c_impl(ir)
        assert 'req_q' in impl


# ---------------------------------------------------------------------------
# queue() factory deprecation
# ---------------------------------------------------------------------------

class TestQueueFactoryDeprecation:
    def test_queue_factory_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            zdc.queue(depth=4)
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_queue_factory_message(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            zdc.queue(depth=4)
        msg = str(caught[0].message)
        assert 'deprecated' in msg.lower()

    def test_queue_factory_still_works(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            result = zdc.queue(depth=4)
        assert result is not None

    def test_queue_factory_invalid_depth_raises(self):
        with pytest.raises(ValueError):
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                zdc.queue(depth=0)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestQueueRegistry:
    def test_queue_registered(self):
        from zuspec.ir.core.registry import global_registry
        reg = global_registry()
        assert reg.get_sv_model(Queue) is not None

    def test_registry_sv_model_is_queue(self):
        from zuspec.ir.core.registry import global_registry
        reg = global_registry()
        assert reg.get_sv_model(Queue) is Queue


# ---------------------------------------------------------------------------
# DataModelFactory hook — Queue[T] alias unwrapping
# ---------------------------------------------------------------------------

class TestQueueFactoryHook:
    def test_factory_intercepts_queue_alias_field(self):
        """A component with Queue[u32] produces an AbstractionFieldIR."""
        from zuspec.dataclasses.data_model_factory import DataModelFactory

        @zdc.dataclass
        class _CompQ(zdc.Component):
            req_q: Queue[zdc.u32] = zdc.inst(Queue, kwargs={'DEPTH': 4})

        ctx = DataModelFactory().build([_CompQ])
        dm = ctx.type_m.get(_CompQ.__name__) or list(ctx.type_m.values())[-1]
        abstraction_fields = [f for f in dm.fields
                               if getattr(f, 'is_abstraction_field', False)]
        assert len(abstraction_fields) == 1
        assert abstraction_fields[0].spec_type_name == 'Queue'

    def test_factory_hook_queue_depth(self):
        from zuspec.dataclasses.data_model_factory import DataModelFactory

        @zdc.dataclass
        class _CompQ2(zdc.Component):
            req_q: Queue[zdc.u32] = zdc.inst(Queue, kwargs={'DEPTH': 16})

        ctx = DataModelFactory().build([_CompQ2])
        dm = ctx.type_m.get(_CompQ2.__name__) or list(ctx.type_m.values())[-1]
        af = next(f for f in dm.fields if getattr(f, 'is_abstraction_field', False))
        assert af.ir_node['depth'] == 16

    def test_factory_hook_element_type_from_subscript(self):
        """Queue[u32] element_type is correctly extracted from the _QueueAlias._item."""
        from zuspec.dataclasses.data_model_factory import DataModelFactory

        @zdc.dataclass
        class _CompQ3(zdc.Component):
            req_q: Queue[zdc.u32] = zdc.inst(Queue, kwargs={'DEPTH': 4})

        ctx = DataModelFactory().build([_CompQ3])
        dm = ctx.type_m.get(_CompQ3.__name__) or list(ctx.type_m.values())[-1]
        af = next(f for f in dm.fields if getattr(f, 'is_abstraction_field', False))
        assert af.ir_node['elem_width'] == 32
