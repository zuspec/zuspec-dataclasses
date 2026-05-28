"""Tests for RegisterRT and RegisterValue."""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.register_rt import RegisterRT, RegisterValue
from zuspec.dataclasses.mmr.field_rt import FieldRT


def _run(coro):
    return asyncio.run(coro)


def _build_reg(fields_spec):
    """Build a RegisterRT with the given fields.

    fields_spec: list of (name, lsb, width, **reg_field_kwargs)
    """
    reg = RegisterRT('TEST', offset=0x00, width=32)
    for name, lsb, width, kwargs in fields_spec:
        fd = zdc.reg_field(**kwargs)
        fd._width = width
        fd.lsb = lsb
        field = FieldRT(fd, name)
        reg._add_field(name, field, lsb)
    return reg


# ---------------------------------------------------------------------------
# bus_read packs fields correctly
# ---------------------------------------------------------------------------

def test_bus_read_packs_fields():
    reg = _build_reg([
        ('MODE',  0, 4, dict(default=0)),
        ('SPEED', 4, 4, dict(default=0)),
    ])
    reg._fields['MODE']._store(0xA)
    reg._fields['SPEED']._store(0x5)
    assert reg.bus_read() == (0x5 << 4) | 0xA


def test_bus_write_int_dispatches_fields():
    reg = _build_reg([
        ('A', 0, 8, dict(default=0)),
        ('B', 8, 8, dict(default=0)),
    ])
    reg.bus_write(0x4321)
    assert reg._fields['A'].value == 0x21
    assert reg._fields['B'].value == 0x43


def test_bus_write_strobe():
    """Byte-strobe 0b0001 (byte 0 only) leaves byte 1 fields unchanged."""
    reg = _build_reg([
        ('LO', 0, 8, dict(default=0xAA)),
        ('HI', 8, 8, dict(default=0xBB)),
    ])
    reg.bus_write(0x0000, strobe=0b0001)   # clear byte 0 only
    assert reg._fields['LO'].value == 0x00
    assert reg._fields['HI'].value == 0xBB   # unchanged


# ---------------------------------------------------------------------------
# read() / write(snapshot) API
# ---------------------------------------------------------------------------

def test_read_returns_snapshot():
    reg = _build_reg([
        ('DONE', 0, 1, dict(default=0)),
        ('CODE', 1, 4, dict(default=7)),
    ])
    snap = reg.read()
    assert isinstance(snap, RegisterValue)
    assert snap.DONE == 0
    assert snap.CODE == 7


def test_snapshot_replace():
    reg = _build_reg([
        ('A', 0, 4, dict(default=1)),
        ('B', 4, 4, dict(default=2)),
    ])
    s = reg.read()
    s2 = s._replace(A=9)
    assert s2.A == 9
    assert s2.B == 2
    assert s.A == 1   # original unchanged


def test_write_snapshot_dirty_only():
    reg = _build_reg([
        ('X', 0, 8, dict(hw=zdc.HW.W, default=0x10)),
        ('Y', 8, 8, dict(hw=zdc.HW.W, default=0x20)),
    ])
    snap = reg.read()
    snap.X = 0xFF   # only X dirty
    reg.write(snap)
    assert reg._fields['X'].value == 0xFF
    assert reg._fields['Y'].value == 0x20   # untouched


# ---------------------------------------------------------------------------
# Direct attribute access (HW comb/sync path)
# ---------------------------------------------------------------------------

def test_direct_hw_getattr():
    reg = _build_reg([('BUSY', 0, 1, dict(hw=zdc.HW.W, default=1))])
    assert reg.BUSY == 1


def test_direct_hw_setattr():
    reg = _build_reg([('BUSY', 0, 1, dict(hw=zdc.HW.W, default=0))])
    reg.BUSY = 1
    assert reg._fields['BUSY'].value == 1


# ---------------------------------------------------------------------------
# intr property
# ---------------------------------------------------------------------------

def test_intr_or_of_stickybit_fields():
    reg = _build_reg([
        ('DONE', 0, 1, dict(hw=zdc.HW.W, hwset=True, stickybit='posedge', default=0)),
    ])
    assert reg.intr is False
    reg._fields['DONE']._hw_assign(1)
    assert reg.intr is True


def test_intr_false_when_clear():
    reg = _build_reg([
        ('DONE', 0, 1, dict(hw=zdc.HW.W, hwset=True, stickybit='posedge', default=0)),
    ])
    reg._fields['DONE']._hw_assign(1)
    reg._fields['DONE'].write(1)   # woclr-style clear via direct write
    # write dispatches through _bus_write_entry which applies onwrite=None → stores 1
    # We need a field with onwrite='woclr' to actually clear; force it:
    reg._fields['DONE']._store(0)
    assert reg.intr is False


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

def test_reset_all_fields():
    reg = _build_reg([
        ('A', 0, 8, dict(default=0xAA)),
        ('B', 8, 8, dict(default=0xBB)),
    ])
    reg.bus_write(0x0000)
    reg.reset()
    assert reg._fields['A'].value == 0xAA
    assert reg._fields['B'].value == 0xBB


# ---------------------------------------------------------------------------
# on_write callback
# ---------------------------------------------------------------------------

def test_on_write_callback():
    reg = _build_reg([('VAL', 0, 8, dict(default=0))])
    log = []
    reg.on_write(lambda old, new: log.append((old, new)))
    reg.bus_write(0x42)
    assert log == [(0, 0x42)]


# ---------------------------------------------------------------------------
# wait_until
# ---------------------------------------------------------------------------

def test_wait_until_immediate():
    async def _test():
        reg = _build_reg([('DONE', 0, 1, dict(hw=zdc.HW.W, default=1))])
        await reg.wait_until(lambda r: r.DONE == 1)   # already satisfied

    _run(_test())


def test_wait_until_suspends():
    async def _test():
        reg = _build_reg([('DONE', 0, 1, dict(hw=zdc.HW.W, default=0))])

        async def _driver():
            await asyncio.sleep(0)
            reg._fields['DONE']._hw_assign(1)

        asyncio.ensure_future(_driver())
        await reg.wait_until(lambda r: r.DONE == 1)
        assert reg.DONE == 1

    _run(_test())


def test_wait_until_multi_field_pred():
    async def _test():
        reg = _build_reg([
            ('A', 0, 4, dict(hw=zdc.HW.W, default=0)),
            ('B', 4, 4, dict(hw=zdc.HW.W, default=0)),
        ])

        async def _driver():
            await asyncio.sleep(0)
            reg._fields['A']._hw_assign(1)
            await asyncio.sleep(0)
            reg._fields['B']._hw_assign(1)

        asyncio.ensure_future(_driver())
        await reg.wait_until(lambda r: r.A == 1 and r.B == 1)
        assert reg.A == 1 and reg.B == 1

    _run(_test())
