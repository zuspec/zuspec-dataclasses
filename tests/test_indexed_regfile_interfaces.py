"""Phase 4 tests — IndexedRegFile lowering-interface implementations.

Tests cover protocol membership, elaborate_field, SV generation, SVA
generation, and DataModelFactory hook integration.
"""
from __future__ import annotations

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import IndexedRegFile, _extract_bit_width, u5, u32
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

def _make_field_ir(field_name='regfile', index=0, read_ports=2, write_ports=1,
                   shared_port=False, element_type=None):
    if element_type is None:
        element_type = (u5, u32)
    return IndexedRegFile.elaborate_field(
        field_name=field_name,
        field_index=index,
        inst_kwargs={
            'READ_PORTS': read_ports,
            'WRITE_PORTS': write_ports,
            'SHARED_PORT': shared_port,
        },
        element_type=element_type,
    )


# ---------------------------------------------------------------------------
# Protocol membership
# ---------------------------------------------------------------------------

class TestIndexedRegFileProtocols:
    def test_indexed_regfile_is_lowerable(self):
        assert Lowerable in IndexedRegFile.__mro__

    def test_indexed_regfile_is_elaboratable(self):
        assert ElaboratableInterface in IndexedRegFile.__mro__

    def test_indexed_regfile_is_sv_emittable(self):
        assert SVEmittableInterface in IndexedRegFile.__mro__

    def test_indexed_regfile_is_sva_emittable(self):
        assert SVAEmittableInterface in IndexedRegFile.__mro__

    def test_indexed_regfile_is_csim_emittable(self):
        assert CSimEmittableInterface in IndexedRegFile.__mro__


# ---------------------------------------------------------------------------
# _extract_bit_width helper
# ---------------------------------------------------------------------------

class TestExtractBitWidth:
    def test_u5_gives_5(self):
        assert _extract_bit_width(u5) == 5

    def test_u32_gives_32(self):
        assert _extract_bit_width(u32) == 32

    def test_non_annotated_returns_default(self):
        assert _extract_bit_width(int, default=16) == 16

    def test_none_returns_default(self):
        assert _extract_bit_width(None, default=8) == 8  # type: ignore


# ---------------------------------------------------------------------------
# elaborate_field
# ---------------------------------------------------------------------------

class TestIndexedRegFileElaborateField:
    def test_returns_abstraction_field_ir(self):
        ir = _make_field_ir()
        assert isinstance(ir, AbstractionFieldIR)

    def test_is_abstraction_field(self):
        ir = _make_field_ir()
        assert ir.is_abstraction_field is True

    def test_field_name_stored(self):
        ir = _make_field_ir(field_name='regs')
        assert ir.field_name == 'regs'
        assert ir.name == 'regs'

    def test_field_index_stored(self):
        ir = _make_field_ir(index=3)
        assert ir.field_index == 3

    def test_spec_type_name(self):
        ir = _make_field_ir()
        assert ir.spec_type_name == 'IndexedRegFile'

    def test_py_cls_is_indexed_regfile(self):
        ir = _make_field_ir()
        assert ir.py_cls is IndexedRegFile

    def test_depth_from_type_args(self):
        # u5 → idx_width=5 → depth=32
        ir = _make_field_ir(element_type=(u5, u32))
        assert ir.ir_node['depth'] == 32

    def test_idx_width_from_type_args(self):
        ir = _make_field_ir(element_type=(u5, u32))
        assert ir.ir_node['idx_width'] == 5

    def test_data_width_from_type_args(self):
        ir = _make_field_ir(element_type=(u5, u32))
        assert ir.ir_node['data_width'] == 32

    def test_read_ports_from_inst_kwargs(self):
        ir = _make_field_ir(read_ports=3)
        assert ir.ir_node['read_ports'] == 3

    def test_write_ports_from_inst_kwargs(self):
        ir = _make_field_ir(write_ports=2)
        assert ir.ir_node['write_ports'] == 2

    def test_shared_port_from_inst_kwargs(self):
        ir = _make_field_ir(shared_port=True)
        assert ir.ir_node['shared_port'] is True

    def test_default_read_ports(self):
        ir = IndexedRegFile.elaborate_field(
            field_name='rf', field_index=0, inst_kwargs={}, element_type=(u5, u32))
        assert ir.ir_node['read_ports'] == 2

    def test_default_write_ports(self):
        ir = IndexedRegFile.elaborate_field(
            field_name='rf', field_index=0, inst_kwargs={}, element_type=(u5, u32))
        assert ir.ir_node['write_ports'] == 1

    def test_default_shared_port(self):
        ir = IndexedRegFile.elaborate_field(
            field_name='rf', field_index=0, inst_kwargs={}, element_type=(u5, u32))
        assert ir.ir_node['shared_port'] is False


# ---------------------------------------------------------------------------
# sv_module_text
# ---------------------------------------------------------------------------

class TestIndexedRegFileSVModule:
    def test_sv_module_text_contains_module(self):
        ir = _make_field_ir()
        sv = IndexedRegFile.sv_module_text(ir)
        assert 'module' in sv

    def test_sv_module_text_contains_endmodule(self):
        ir = _make_field_ir()
        sv = IndexedRegFile.sv_module_text(ir)
        assert 'endmodule' in sv

    def test_sv_module_text_2r1w_topology(self):
        ir = _make_field_ir(read_ports=2, write_ports=1, shared_port=False)
        sv = IndexedRegFile.sv_module_text(ir)
        assert '2r1w' in sv.lower() or 'read' in sv.lower()

    def test_sv_module_text_sdp_topology(self):
        ir = _make_field_ir(read_ports=1, write_ports=1, shared_port=False)
        sv = IndexedRegFile.sv_module_text(ir)
        assert 'module' in sv

    def test_sv_module_text_1p_topology(self):
        ir = _make_field_ir(read_ports=1, write_ports=1, shared_port=True)
        sv = IndexedRegFile.sv_module_text(ir)
        assert 'module' in sv


# ---------------------------------------------------------------------------
# sv_instance_text
# ---------------------------------------------------------------------------

class TestIndexedRegFileSVInstance:
    def test_instance_text_contains_field_name(self):
        ir = _make_field_ir(field_name='regfile')
        txt = IndexedRegFile.sv_instance_text(ir)
        assert 'regfile' in txt

    def test_instance_text_contains_clk(self):
        ir = _make_field_ir()
        txt = IndexedRegFile.sv_instance_text(ir)
        assert 'clk' in txt

    def test_instance_text_contains_rst(self):
        ir = _make_field_ir()
        txt = IndexedRegFile.sv_instance_text(ir)
        assert 'rst' in txt

    def test_shared_port_single_bus(self):
        ir = _make_field_ir(shared_port=True)
        txt = IndexedRegFile.sv_instance_text(ir)
        assert 'rd_en(' in txt
        assert 'rd_en_0' not in txt


# ---------------------------------------------------------------------------
# rewrite_proc_stmts
# ---------------------------------------------------------------------------

class TestIndexedRegFileRewriteProc:
    def test_rewrite_is_passthrough(self):
        ir = _make_field_ir()
        stmts = ['stmt_a', 'stmt_b']
        result = IndexedRegFile.rewrite_proc_stmts(stmts, ir)
        assert result == stmts


# ---------------------------------------------------------------------------
# sva_assert_properties
# ---------------------------------------------------------------------------

class TestIndexedRegFileSVA:
    def test_sva_2r1w_generates_two_raw_props(self):
        ir = _make_field_ir(read_ports=2, write_ports=1, shared_port=False)
        props = IndexedRegFile.sva_assert_properties(ir)
        assert len(props) == 2  # 2 read × 1 write

    def test_sva_raw_property_contains_field_name(self):
        ir = _make_field_ir(field_name='rf', read_ports=1, write_ports=1)
        props = IndexedRegFile.sva_assert_properties(ir)
        assert len(props) == 1
        assert 'rf' in props[0]

    def test_sva_shared_port_no_raw_props(self):
        ir = _make_field_ir(shared_port=True)
        props = IndexedRegFile.sva_assert_properties(ir)
        assert props == []

    def test_sva_assume_properties_empty(self):
        ir = _make_field_ir()
        assert IndexedRegFile.sva_assume_properties(ir) == []

    def test_bmc_depth(self):
        ir = _make_field_ir()
        assert IndexedRegFile.bmc_depth(ir) == 4

    def test_cutpoint_signals_empty(self):
        ir = _make_field_ir()
        assert IndexedRegFile.cutpoint_signals(ir) == []


# ---------------------------------------------------------------------------
# c_header / c_impl
# ---------------------------------------------------------------------------

class TestIndexedRegFileCGen:
    def test_c_header_contains_field_name(self):
        ir = _make_field_ir(field_name='regfile')
        h = IndexedRegFile.c_header(ir)
        assert 'regfile' in h

    def test_c_header_has_include_guard(self):
        ir = _make_field_ir(field_name='regfile')
        h = IndexedRegFile.c_header(ir)
        assert '#ifndef' in h and '#define' in h and '#endif' in h

    def test_c_impl_contains_array_decl(self):
        ir = _make_field_ir(field_name='regfile')
        impl = IndexedRegFile.c_impl(ir)
        assert 'zdc_regfile_rf' in impl


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestIndexedRegFileRegistry:
    def test_indexed_regfile_registered(self):
        from zuspec.ir.core.registry import global_registry
        reg = global_registry()
        assert reg.get_sv_model(IndexedRegFile) is not None

    def test_registry_sv_model_is_indexed_regfile(self):
        from zuspec.ir.core.registry import global_registry
        reg = global_registry()
        assert reg.get_sv_model(IndexedRegFile) is IndexedRegFile


# ---------------------------------------------------------------------------
# DataModelFactory hook
# ---------------------------------------------------------------------------

class TestIndexedRegFileFactoryHook:
    def test_factory_intercepts_indexed_regfile_field(self):
        """A component with IndexedRegFile[u5, u32] produces an AbstractionFieldIR."""
        from zuspec.dataclasses.data_model_factory import DataModelFactory

        @zdc.dataclass
        class _Comp(zdc.Component):
            rf: IndexedRegFile[zdc.u5, zdc.u32] = zdc.indexed_regfile(
                read_ports=2, write_ports=1)

        ctx = DataModelFactory().build([_Comp])
        dm = ctx.type_m.get(_Comp.__name__) or list(ctx.type_m.values())[-1]
        abstraction_fields = [f for f in dm.fields
                               if getattr(f, 'is_abstraction_field', False)]
        assert len(abstraction_fields) == 1
        assert abstraction_fields[0].spec_type_name == 'IndexedRegFile'

    def test_factory_hook_stores_correct_dimensions(self):
        from zuspec.dataclasses.data_model_factory import DataModelFactory

        @zdc.dataclass
        class _Comp2(zdc.Component):
            rf: IndexedRegFile[zdc.u5, zdc.u32] = zdc.indexed_regfile(
                read_ports=2, write_ports=1)

        ctx = DataModelFactory().build([_Comp2])
        dm = ctx.type_m.get(_Comp2.__name__) or list(ctx.type_m.values())[-1]
        af = next(f for f in dm.fields if getattr(f, 'is_abstraction_field', False))
        assert af.ir_node['depth'] == 32
        assert af.ir_node['idx_width'] == 5
        assert af.ir_node['data_width'] == 32
        assert af.ir_node['read_ports'] == 2
