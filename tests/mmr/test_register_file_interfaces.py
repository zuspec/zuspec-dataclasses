"""Tests for RegisterFile lowering-interface implementations (Phase 3)."""
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.base import RegisterFile
from zuspec.ir.core.interfaces import (
    Lowerable,
    ElaboratableInterface,
    SVEmittableInterface,
    SVAEmittableInterface,
    CSimEmittableInterface,
)
from zuspec.ir.core.abstraction_field_ir import AbstractionFieldIR


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@zdc.regfile
class _SimpleRegs(RegisterFile):
    @zdc.reg(offset=0x00)
    class CTRL:
        EN: zdc.u1 = zdc.reg_field(default=0)


@zdc.regfile
class _SinglepulseRegs(RegisterFile):
    @zdc.reg(offset=0x00)
    class CMD:
        START: zdc.u1 = zdc.reg_field(singlepulse=True, default=0)


def _make_field_ir(regfile_cls=_SimpleRegs, field_name='regs', index=0):
    return regfile_cls.elaborate_field(field_name, index, {})


# ---------------------------------------------------------------------------
# Protocol membership
# ---------------------------------------------------------------------------

class TestRegisterFileProtocols:
    def test_regfile_is_lowerable(self):
        assert isinstance(RegisterFile, type)
        assert Lowerable in RegisterFile.__mro__

    def test_regfile_is_elaboratable(self):
        assert ElaboratableInterface in RegisterFile.__mro__

    def test_regfile_is_sv_emittable(self):
        assert SVEmittableInterface in RegisterFile.__mro__

    def test_regfile_is_sva_emittable(self):
        assert SVAEmittableInterface in RegisterFile.__mro__

    def test_regfile_is_csim_emittable(self):
        assert CSimEmittableInterface in RegisterFile.__mro__


# ---------------------------------------------------------------------------
# elaborate_field
# ---------------------------------------------------------------------------

class TestElaborateField:
    def test_elaborate_field_produces_abstraction_ir(self):
        field_ir = _make_field_ir()
        assert isinstance(field_ir, AbstractionFieldIR)

    def test_elaborate_field_spec_type_name(self):
        field_ir = _make_field_ir()
        assert field_ir.spec_type_name == 'RegisterFile'

    def test_elaborate_field_field_name_preserved(self):
        field_ir = _make_field_ir(field_name='my_regs')
        assert field_ir.field_name == 'my_regs'

    def test_elaborate_field_ir_node_has_reg_classes(self):
        field_ir = _make_field_ir()
        reg_classes = field_ir.ir_node.get('reg_classes', [])
        assert len(reg_classes) > 0

    def test_elaborate_field_ir_node_has_module_name(self):
        field_ir = _make_field_ir()
        assert 'module_name' in field_ir.ir_node
        assert isinstance(field_ir.ir_node['module_name'], str)

    def test_elaborate_field_ir_node_has_regfile_cls(self):
        field_ir = _make_field_ir()
        assert field_ir.ir_node['regfile_cls'] is _SimpleRegs


# ---------------------------------------------------------------------------
# sv_module_text
# ---------------------------------------------------------------------------

class TestSvModuleText:
    def test_sv_module_text_contains_module_keyword(self):
        field_ir = _make_field_ir()
        sv = RegisterFile.sv_module_text(field_ir)
        assert "module" in sv

    def test_sv_module_text_non_empty(self):
        field_ir = _make_field_ir()
        sv = RegisterFile.sv_module_text(field_ir)
        assert len(sv.strip()) > 0


# ---------------------------------------------------------------------------
# sv_instance_text
# ---------------------------------------------------------------------------

class TestSvInstanceText:
    def test_sv_instance_text_non_empty(self):
        field_ir = _make_field_ir()
        text = RegisterFile.sv_instance_text(field_ir, '')
        assert len(text.strip()) > 0

    def test_sv_instance_text_contains_field_name(self):
        field_ir = _make_field_ir(field_name='regs')
        text = RegisterFile.sv_instance_text(field_ir, '')
        assert 'regs' in text


# ---------------------------------------------------------------------------
# rewrite_proc_stmts
# ---------------------------------------------------------------------------

class TestRewriteProcStmts:
    def test_rewrite_proc_stmts_passthrough(self):
        field_ir = _make_field_ir()
        stmts = ['stmt1', 'stmt2']
        result = RegisterFile.rewrite_proc_stmts(stmts, field_ir)
        assert result is stmts


# ---------------------------------------------------------------------------
# SVA properties
# ---------------------------------------------------------------------------

class TestSvaProperties:
    def test_sva_assume_properties_empty(self):
        field_ir = _make_field_ir()
        assert RegisterFile.sva_assume_properties(field_ir) == []

    def test_sva_assert_properties_no_singlepulse(self):
        field_ir = _make_field_ir()
        props = RegisterFile.sva_assert_properties(field_ir)
        assert isinstance(props, list)
        assert props == []

    def test_sva_singlepulse_property_generated(self):
        field_ir = _make_field_ir(_SinglepulseRegs)
        props = RegisterFile.sva_assert_properties(field_ir)
        assert len(props) > 0
        assert any('|=>' in p for p in props)

    def test_bmc_depth_is_zero(self):
        field_ir = _make_field_ir()
        assert RegisterFile.bmc_depth(field_ir) == 0

    def test_cutpoint_signals_empty(self):
        field_ir = _make_field_ir()
        assert RegisterFile.cutpoint_signals(field_ir) == []


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registerfile_in_global_registry(self):
        from zuspec.ir.core.registry import global_registry
        r = global_registry()
        assert r.get_sv_model('RegisterFile') is not None
