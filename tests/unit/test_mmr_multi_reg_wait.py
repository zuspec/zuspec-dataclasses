"""Tests for cross-register wait_until free function."""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.register_rt import RegisterRT
from zuspec.dataclasses.mmr.field_rt import FieldRT
from zuspec.dataclasses.mmr.wait import wait_until


def _run(coro):
    return asyncio.run(coro)


def _build_reg(name, fields_spec):
    reg = RegisterRT(name, offset=0, width=32)
    for fname, lsb, width, kwargs in fields_spec:
        fd = zdc.reg_field(**kwargs)
        fd._width = width
        fd.lsb = lsb
        field = FieldRT(fd, fname)
        reg._add_field(fname, field, lsb)
    return reg


def test_wait_until_two_regs():
    async def _test():
        ra = _build_reg('A', [('X', 0, 8, dict(hw=zdc.HW.W, default=0))])
        rb = _build_reg('B', [('Y', 0, 8, dict(hw=zdc.HW.W, default=0))])

        async def _driver():
            await asyncio.sleep(0)
            ra._fields['X']._hw_assign(1)
            await asyncio.sleep(0)
            rb._fields['Y']._hw_assign(1)

        asyncio.ensure_future(_driver())
        await wait_until(ra, rb, lambda a, b: a.X == 1 and b.Y == 1)
        assert ra.X == 1 and rb.Y == 1

    _run(_test())


def test_wait_until_wakes_on_either_reg_change():
    async def _test():
        ra = _build_reg('A', [('X', 0, 8, dict(hw=zdc.HW.W, default=0))])
        rb = _build_reg('B', [('Y', 0, 8, dict(hw=zdc.HW.W, default=0))])
        woke = []

        async def _waiter():
            await wait_until(ra, rb, lambda a, b: a.X == 7 or b.Y == 7)
            woke.append(True)

        asyncio.ensure_future(_waiter())
        await asyncio.sleep(0)
        rb._fields['Y']._hw_assign(7)   # only B changes
        for _ in range(3):
            await asyncio.sleep(0)
        assert len(woke) == 1

    _run(_test())


def test_wait_until_reparks_if_pred_unsatisfied():
    async def _test():
        ra = _build_reg('A', [('X', 0, 8, dict(hw=zdc.HW.W, default=0))])
        rb = _build_reg('B', [('Y', 0, 8, dict(hw=zdc.HW.W, default=0))])
        woke = []

        async def _waiter():
            await wait_until(ra, rb, lambda a, b: a.X == 1 and b.Y == 1)
            woke.append(True)

        asyncio.ensure_future(_waiter())
        await asyncio.sleep(0)
        ra._fields['X']._hw_assign(1)   # pred not satisfied (B still 0)
        for _ in range(3):
            await asyncio.sleep(0)
        assert len(woke) == 0   # still parked

        rb._fields['Y']._hw_assign(1)   # now both satisfied
        for _ in range(3):
            await asyncio.sleep(0)
        assert len(woke) == 1

    _run(_test())
