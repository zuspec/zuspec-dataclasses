"""Tests for reg_field() descriptor and FieldAttr presets."""
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.descriptor import FieldDescriptor, _Preset


# ---------------------------------------------------------------------------
# reg_field() defaults and validation
# ---------------------------------------------------------------------------

def test_reg_field_defaults():
    fd = zdc.reg_field()
    assert fd.sw == zdc.SW.RW
    assert fd.hw == zdc.HW.R
    assert fd.onwrite is None
    assert fd.onread is None
    assert fd.singlepulse is False
    assert fd.stickybit is False
    assert fd.default == 0
    assert fd._width is None


def test_reg_field_custom_values():
    fd = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W, onwrite='woclr', default=7)
    assert fd.sw == zdc.SW.RO
    assert fd.hw == zdc.HW.W
    assert fd.onwrite == 'woclr'
    assert fd.default == 7


def test_reg_field_bad_onwrite():
    with pytest.raises(ValueError, match="onwrite"):
        zdc.reg_field(onwrite='invalid')


def test_reg_field_bad_onread():
    with pytest.raises(ValueError, match="onread"):
        zdc.reg_field(onread='bad')


def test_reg_field_bad_precedence():
    with pytest.raises(ValueError, match="precedence"):
        zdc.reg_field(precedence='none')


# ---------------------------------------------------------------------------
# @zdc.reg width injection from zdc.uN annotation
# ---------------------------------------------------------------------------

def test_reg_field_width_injected():
    @zdc.reg(offset=0x00)
    class REG:
        FIELD: zdc.u8 = zdc.reg_field(default=0xFF)

    assert REG._mmr_fields[0][1]._width == 8
    assert REG._mmr_fields[0][1].default == 0xFF


def test_reg_field_auto_lsb_packed():
    @zdc.reg(offset=0x00)
    class REG:
        A: zdc.u4 = zdc.reg_field()
        B: zdc.u8 = zdc.reg_field()
        C: zdc.u4 = zdc.reg_field()

    fields = {name: fd for name, fd in REG._mmr_fields}
    assert fields['A'].lsb == 0
    assert fields['B'].lsb == 4
    assert fields['C'].lsb == 12


def test_reg_field_explicit_lsb():
    @zdc.reg(offset=0x00)
    class REG:
        A: zdc.u4 = zdc.reg_field(lsb=8)

    assert REG._mmr_fields[0][1].lsb == 8


def test_reg_field_overlap_error():
    with pytest.raises(ValueError, match="overlap"):
        @zdc.reg(offset=0x00)
        class REG:
            A: zdc.u8 = zdc.reg_field(lsb=0)
            B: zdc.u8 = zdc.reg_field(lsb=4)   # overlaps with A at bits 4-7


def test_reg_field_beyond_width_error():
    with pytest.raises(ValueError, match="beyond register width"):
        @zdc.reg(offset=0x00, width=8)
        class REG:
            A: zdc.u8 = zdc.reg_field(lsb=4)   # bits 4-11, exceeds 8-bit reg


# ---------------------------------------------------------------------------
# FieldAttr presets
# ---------------------------------------------------------------------------

def test_fieldattr_rw_bare():
    assert isinstance(zdc.FieldAttr.RW, _Preset)


def test_fieldattr_rw_with_default():
    fd = zdc.FieldAttr.RW(default=5)
    assert isinstance(fd, FieldDescriptor)
    assert fd.sw == zdc.SW.RW
    assert fd.hw == zdc.HW.R
    assert fd.default == 5


def test_fieldattr_ro():
    fd = zdc.FieldAttr.RO._to_descriptor()
    assert fd.sw == zdc.SW.RO
    assert fd.hw == zdc.HW.W
    assert fd.hwset is True
    assert fd.hwclr is True


def test_fieldattr_w1s():
    fd = zdc.FieldAttr.W1S._to_descriptor()
    assert fd.onwrite == 'woset'
    assert fd.hw == zdc.HW.RW


def test_fieldattr_w1c():
    fd = zdc.FieldAttr.W1C._to_descriptor()
    assert fd.onwrite == 'woclr'
    assert fd.hwset is True


def test_fieldattr_wo():
    fd = zdc.FieldAttr.WO._to_descriptor()
    assert fd.sw == zdc.SW.WO
    assert fd.hw == zdc.HW.R


def test_fieldattr_pulse():
    fd = zdc.FieldAttr.Pulse._to_descriptor()
    assert fd.singlepulse is True


def test_fieldattr_stickybit():
    fd = zdc.FieldAttr.StickyBit._to_descriptor()
    assert fd.stickybit == 'posedge'
    assert fd.onwrite == 'woclr'
    assert fd.hwset is True
    assert fd.hw == zdc.HW.W


def test_fieldattr_stickybit_bare_in_reg():
    @zdc.reg(offset=0x00)
    class REG:
        DONE: zdc.u1 = zdc.FieldAttr.StickyBit

    _, fd = REG._mmr_fields[0]
    assert fd.stickybit == 'posedge'
    assert fd._width == 1
