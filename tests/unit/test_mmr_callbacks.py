"""Tests for FieldRT callback system."""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.field_rt import FieldRT


def _run(coro):
    return asyncio.run(coro)


def _make_field(width=8, **kwargs) -> FieldRT:
    fd = zdc.reg_field(**kwargs)
    fd._width = width
    return FieldRT(fd, 'TEST')


def test_on_write_fires_on_sw_write():
    f = _make_field(width=8, default=0)
    log = []
    f.on_write(lambda old, new: log.append((old, new)))
    f.write(0x42)
    assert log == [(0, 0x42)]


def test_on_write_silent_on_hw_write():
    f = _make_field(width=8, hw=zdc.HW.W, default=0)
    log = []
    f.on_write(lambda old, new: log.append(new))
    f._hw_assign(0x42)
    assert log == []   # on_write only fires from SW path


def test_on_hw_write_fires_on_hw_assign():
    f = _make_field(width=8, hw=zdc.HW.W, default=0)
    log = []
    f.on_hw_write(lambda old, new: log.append((old, new)))
    f._hw_assign(0x42)
    assert log == [(0, 0x42)]


def test_on_hw_write_silent_on_sw_write():
    f = _make_field(width=8, default=0)
    log = []
    f.on_hw_write(lambda old, new: log.append(new))
    f.write(0x42)
    assert log == []


def test_on_change_fires_on_sw_path():
    f = _make_field(width=8, default=0)
    log = []
    f.on_change(lambda old, new: log.append(('sw', old, new)))
    f.write(5)
    assert log == [('sw', 0, 5)]


def test_on_change_fires_on_hw_path():
    f = _make_field(width=8, hw=zdc.HW.W, default=0)
    log = []
    f.on_change(lambda old, new: log.append(('hw', old, new)))
    f._hw_assign(5)
    assert log == [('hw', 0, 5)]


def test_on_change_silent_if_value_unchanged():
    f = _make_field(width=8, default=5)
    log = []
    f.on_change(lambda old, new: log.append(new))
    f.write(5)   # same value
    assert log == []


def test_on_swmod_fires_only_when_value_changes():
    f = _make_field(width=8, default=0)
    log = []
    f.on_swmod(lambda: log.append(True))
    f.write(1)   # changes value
    assert len(log) == 1
    f.write(1)   # same value
    assert len(log) == 1


def test_write_handle_cancel():
    f = _make_field(width=8, default=0)
    log = []
    handle = f.on_write(lambda old, new: log.append(new))
    f.write(1)
    handle.cancel()
    f.write(2)
    assert log == [1]   # only the first write recorded


def test_cancel_idempotent():
    f = _make_field(width=8, default=0)
    handle = f.on_write(lambda o, n: None)
    handle.cancel()
    handle.cancel()   # second cancel must not raise


def test_multiple_callbacks_fire_in_order():
    f = _make_field(width=8, default=0)
    order = []
    f.on_write(lambda o, n: order.append('first'))
    f.on_write(lambda o, n: order.append('second'))
    f.write(1)
    assert order == ['first', 'second']
