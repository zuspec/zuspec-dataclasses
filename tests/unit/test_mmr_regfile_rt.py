"""Tests for @zdc.regfile decorator and RegisterFile base class."""
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.base import RegisterFile
from zuspec.dataclasses.mmr.bus.passthrough import PassthroughPort


# ---------------------------------------------------------------------------
# Shared fixture register file
# ---------------------------------------------------------------------------

@zdc.regfile
class _TestRegs(RegisterFile):

    @zdc.reg(offset=0x00)
    class CTRL:
        START: zdc.u1 = zdc.reg_field(singlepulse=True, default=0)
        MODE:  zdc.u4 = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.R, default=0)

    @zdc.reg(offset=0x04)
    class STATUS:
        BUSY: zdc.u1 = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W, hwset=True,
                                      hwclr=True, default=0)
        DONE: zdc.u1 = zdc.FieldAttr.StickyBit


# ---------------------------------------------------------------------------
# Declaration and elaboration
# ---------------------------------------------------------------------------

def test_regfile_declaration():
    rf = _TestRegs()
    assert 'CTRL' in rf._reg_by_name
    assert 'STATUS' in rf._reg_by_name
    assert 0x00 in rf._reg_map
    assert 0x04 in rf._reg_map


def test_regfile_field_width_preserved():
    rf = _TestRegs()
    assert rf._reg_by_name['CTRL']._fields['MODE']._width == 4


def test_regfile_field_default_preserved():
    rf = _TestRegs()
    assert rf._reg_by_name['CTRL']._fields['MODE'].value == 0


# ---------------------------------------------------------------------------
# Bus write / read
# ---------------------------------------------------------------------------

def test_bus_write_dispatches():
    rf = _TestRegs()
    rf.bus_write(0x00, 0b01110)   # MODE=7, START=0
    assert rf._reg_by_name['CTRL']._fields['MODE'].value == 7


def test_bus_read_applies_onread():
    rf = _TestRegs()
    # DONE is stickybit; set it via hw, then bus_read should not clear (onread=None)
    rf._reg_by_name['STATUS']._fields['DONE']._hw_assign(1)
    v = rf.bus_read(0x04)
    assert (v >> 1) & 1 == 1   # DONE at bit 1 (BUSY is bit 0)
    # onread=None so value unchanged
    assert rf._reg_by_name['STATUS']._fields['DONE'].value == 1


def test_bus_write_decode_miss():
    rf = _TestRegs()
    rf.bus_write(0x99, 0xABCD)   # unknown offset — should not raise
    # No side effect expected


def test_bus_read_decode_miss():
    rf = _TestRegs()
    assert rf.bus_read(0x99) == 0


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def test_reset_all_regs():
    rf = _TestRegs()
    rf.bus_write(0x00, 0xFF)
    rf._reg_by_name['STATUS']._fields['DONE']._hw_assign(1)
    rf.reset()
    assert rf._reg_by_name['CTRL']._fields['MODE'].value == 0
    assert rf._reg_by_name['STATUS']._fields['DONE'].value == 0


# ---------------------------------------------------------------------------
# Named access
# ---------------------------------------------------------------------------

def test_named_reg_access():
    rf = _TestRegs()
    assert rf.CTRL is rf._reg_by_name['CTRL']


def test_named_field_access():
    rf = _TestRegs()
    rf.CTRL.MODE == 0   # attribute access via RegisterRT.__getattr__


def test_named_access_missing():
    rf = _TestRegs()
    with pytest.raises(AttributeError):
        _ = rf.NONEXISTENT


# ---------------------------------------------------------------------------
# PassthroughPort
# ---------------------------------------------------------------------------

def test_passthrough_port_write_read():
    rf = _TestRegs()
    port = PassthroughPort()
    rf.connect(port)
    port.write(0x00, 0b01110)   # MODE=7
    assert rf.CTRL.MODE == 7
    v = port.read(0x00)
    assert (v >> 1) & 0xF == 7   # MODE at bits [4:1]


def test_passthrough_port_read_unknown():
    rf = _TestRegs()
    port = PassthroughPort()
    rf.connect(port)
    assert port.read(0xFF) == 0   # decode miss → 0


def test_multiple_instances_independent():
    """Each RegisterFile instance has independent field state."""
    rf1 = _TestRegs()
    rf2 = _TestRegs()
    rf1.bus_write(0x00, 0b01110)   # set MODE in rf1
    assert rf1.CTRL.MODE == 7
    assert rf2.CTRL.MODE == 0   # rf2 untouched


# ---------------------------------------------------------------------------
# Tests from plan §7.8
# ---------------------------------------------------------------------------

def test_reset_wakes_waiters():
    """After reset(), a coroutine parked on wait_until is re-evaluated."""
    import asyncio

    async def _test():
        rf = _TestRegs()
        # HW sets BUSY=1
        rf.STATUS._fields['BUSY']._hw_assign(1)
        assert rf.STATUS.BUSY == 1

        # Park a coroutine waiting for BUSY == 0
        woke = asyncio.Event()

        async def _waiter():
            await rf.STATUS.wait_until(lambda r: r.BUSY == 0)
            woke.set()

        asyncio.ensure_future(_waiter())
        await asyncio.sleep(0)   # let waiter park
        assert not woke.is_set()

        # Reset the register file → BUSY returns to default=0 → waiter wakes
        rf.reset()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert woke.is_set()

    asyncio.run(_test())
