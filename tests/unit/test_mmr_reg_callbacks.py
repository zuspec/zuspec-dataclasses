"""§7.9 — register-level observable-signal tests.

Tests the ``RegisterRT.on_write`` callback API, which is the simulation
equivalent of the ``swmod`` / ``write`` observable signals described in the
design document.  These callbacks are fired from the bus-side (SW) write path
only; hardware ``_hw_assign`` calls do not trigger them.
"""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.base import RegisterFile


# ---------------------------------------------------------------------------
# Shared register file fixture
# ---------------------------------------------------------------------------

@zdc.regfile
class SimpleRegs(RegisterFile):

    @zdc.reg(offset=0x00)
    class CTRL:
        CMD:    zdc.u8  = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.R,  default=0)
        FLAGS:  zdc.u8  = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.RW, default=0)

    @zdc.reg(offset=0x04)
    class STATUS:
        LEVEL:  zdc.u8  = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W,  default=0)
        DONE:   zdc.u1  = zdc.FieldAttr.StickyBit


def _make_regs() -> SimpleRegs:
    return SimpleRegs()


# ---------------------------------------------------------------------------
# Register-level on_write tests (plan §7.9: test_write_bind)
# ---------------------------------------------------------------------------

def test_reg_on_write_fires_on_bus_write():
    """on_write callback fires when the register is bus-written."""
    regs = _make_regs()
    log = []
    regs.CTRL.on_write(lambda old, new: log.append((old, new)))
    regs.CTRL.bus_write(0x0042)
    assert len(log) == 1


def test_reg_on_write_delivers_old_and_new_words():
    """on_write callback receives correct (old_word, new_word) packed integers."""
    regs = _make_regs()
    log = []
    regs.CTRL.on_write(lambda old, new: log.append((old, new)))
    regs.CTRL.bus_write(0x00FF)   # CMD=0xFF, FLAGS=0x00
    assert log[0] == (0x0000, 0x00FF)


def test_reg_on_write_fires_even_if_value_unchanged():
    """on_write fires for every bus write, even when the value does not change."""
    regs = _make_regs()
    regs.CTRL.bus_write(0x0042)   # prime the register
    log = []
    regs.CTRL.on_write(lambda old, new: log.append((old, new)))
    regs.CTRL.bus_write(0x0042)   # same value again
    assert len(log) == 1


def test_reg_on_write_multiple_callbacks():
    """Multiple on_write callbacks are all invoked, in registration order."""
    regs = _make_regs()
    order = []
    regs.CTRL.on_write(lambda o, n: order.append('first'))
    regs.CTRL.on_write(lambda o, n: order.append('second'))
    regs.CTRL.bus_write(0x01)
    assert order == ['first', 'second']


def test_reg_on_write_cancel_stops_future_calls():
    """Cancelling the returned handle deregisters the callback."""
    regs = _make_regs()
    log = []
    handle = regs.CTRL.on_write(lambda o, n: log.append(n))
    regs.CTRL.bus_write(0x01)
    handle.cancel()
    regs.CTRL.bus_write(0x02)
    assert log == [0x01]   # only the first write recorded


def test_reg_on_write_cancel_idempotent():
    """Cancelling a handle twice must not raise."""
    regs = _make_regs()
    handle = regs.CTRL.on_write(lambda o, n: None)
    handle.cancel()
    handle.cancel()   # should not raise


# ---------------------------------------------------------------------------
# test_bind_not_called_on_hw_write (plan §7.9)
# ---------------------------------------------------------------------------

def test_reg_on_write_silent_for_hw_assign():
    """on_write is NOT fired by hardware _hw_assign; only SW bus path fires it."""
    regs = _make_regs()
    log = []
    regs.CTRL.on_write(lambda o, n: log.append(n))
    # HW direct write — must not fire the SW callback
    regs.CTRL._fields['FLAGS']._hw_assign(0xFF)
    assert log == []


def test_reg_on_write_silent_for_snapshot_write():
    """on_write is NOT fired by RegisterRT.write(snapshot); that is an HW path."""
    regs = _make_regs()
    log = []
    regs.CTRL.on_write(lambda o, n: log.append(n))
    snap = regs.CTRL.read()
    snap.FLAGS = 0xAB
    regs.CTRL.write(snap)
    assert log == []


# ---------------------------------------------------------------------------
# swmod (field-level) tests (plan §7.9: test_swmod_bind)
# ---------------------------------------------------------------------------

def test_field_swmod_fires_on_sw_modifying_write():
    """on_swmod callback fires when SW write changes the field value."""
    regs = _make_regs()
    log = []
    regs.CTRL._fields['CMD'].on_swmod(lambda: log.append(True))
    regs.CTRL._fields['CMD'].write(0x01)
    assert log == [True]


def test_field_swmod_silent_on_no_change():
    """on_swmod does NOT fire when SW write leaves the value unchanged."""
    regs = _make_regs()
    regs.CTRL._fields['CMD'].write(0x55)   # prime
    log = []
    regs.CTRL._fields['CMD'].on_swmod(lambda: log.append(True))
    regs.CTRL._fields['CMD'].write(0x55)   # same value
    assert log == []


def test_field_swmod_silent_on_hw_write():
    """on_swmod does NOT fire for hardware _hw_assign calls."""
    regs = _make_regs()
    log = []
    regs.CTRL._fields['FLAGS'].on_swmod(lambda: log.append(True))
    regs.CTRL._fields['FLAGS']._hw_assign(0xFF)
    assert log == []


def test_field_swmod_multiple_fields_independent():
    """swmod callbacks on different fields are independent."""
    regs = _make_regs()
    cmd_log = []
    flags_log = []
    regs.CTRL._fields['CMD'].on_swmod(lambda: cmd_log.append(True))
    regs.CTRL._fields['FLAGS'].on_swmod(lambda: flags_log.append(True))
    regs.CTRL._fields['CMD'].write(1)
    assert cmd_log == [True]
    assert flags_log == []


# ---------------------------------------------------------------------------
# Register-level write delivers updated word (after multi-field interaction)
# ---------------------------------------------------------------------------

def test_reg_on_write_word_reflects_all_fields():
    """new_word in on_write callback packs all fields after the write."""
    regs = _make_regs()
    # Prime FLAGS=0xAA via HW
    regs.CTRL._fields['FLAGS']._hw_assign(0xAA)
    log = []
    regs.CTRL.on_write(lambda old, new: log.append((old, new)))
    # SW writes CMD=0x11 only (FLAGS stays 0xAA)
    regs.CTRL.bus_write(0xAA11)   # FLAGS=0xAA<<8, CMD=0x11
    old_word, new_word = log[0]
    assert new_word & 0xFF == 0x11          # CMD bits
    assert (new_word >> 8) & 0xFF == 0xAA   # FLAGS bits preserved
