"""Tests for field-level async wait methods."""
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


# ---------------------------------------------------------------------------

def test_wait_value_already_satisfied():
    async def _test():
        f = _make_field(width=8, default=5)
        await f.wait(5)   # already 5 — should return immediately

    _run(_test())


def test_wait_value_suspends_wakes():
    async def _test():
        f = _make_field(width=8, default=0)

        async def _driver():
            await asyncio.sleep(0)
            f.write(42)

        asyncio.ensure_future(_driver())
        await f.wait(42)
        assert f.value == 42

    _run(_test())


def test_wait_set_wakes_on_nonzero():
    async def _test():
        f = _make_field(width=8, default=0)

        async def _driver():
            await asyncio.sleep(0)
            f.write(1)

        asyncio.ensure_future(_driver())
        await f.wait_set()
        assert f.value != 0

    _run(_test())


def test_wait_clear_wakes_on_zero():
    async def _test():
        f = _make_field(width=8, default=5)

        async def _driver():
            await asyncio.sleep(0)
            f.write(0)

        asyncio.ensure_future(_driver())
        await f.wait_clear()
        assert f.value == 0

    _run(_test())


def test_wait_ne_wakes_on_any_change():
    async def _test():
        f = _make_field(width=8, default=3)

        async def _driver():
            await asyncio.sleep(0)
            f.write(7)

        asyncio.ensure_future(_driver())
        await f.wait_ne(3)
        assert f.value != 3

    _run(_test())


def test_wait_any_write_fires_on_noop_write():
    """wait_any_write fires even when value does not change."""
    async def _test():
        f = _make_field(width=8, default=5)
        done = []

        async def _waiter():
            await f.wait_any_write()
            done.append(True)

        asyncio.ensure_future(_waiter())
        await asyncio.sleep(0)   # let waiter park
        f.write(5)               # same value — noop write
        await asyncio.sleep(0)   # let waiter wake
        assert len(done) == 1

    _run(_test())


def test_multiple_waiters_all_wake():
    """Three coroutines waiting on same field all receive the wake."""
    async def _test():
        f = _make_field(width=8, default=0)
        done = []

        async def _waiter(target):
            await f.wait(target)
            done.append(target)

        asyncio.ensure_future(_waiter(1))
        asyncio.ensure_future(_waiter(1))
        asyncio.ensure_future(_waiter(1))
        await asyncio.sleep(0)   # let all waiters park
        f.write(1)
        for _ in range(5):
            await asyncio.sleep(0)
        assert len(done) == 3

    _run(_test())


def test_multiple_waiters_repark():
    """Waiters with different targets: first wakes on match, others repark."""
    async def _test():
        f = _make_field(width=8, default=0)
        woke = []

        async def _waiter(target):
            await f.wait(target)
            woke.append(target)

        asyncio.ensure_future(_waiter(1))
        asyncio.ensure_future(_waiter(2))
        await asyncio.sleep(0)
        f.write(1)              # only waiter(1) should wake
        for _ in range(3):
            await asyncio.sleep(0)
        assert 1 in woke
        assert 2 not in woke   # still parked

        f.write(2)              # now waiter(2) wakes
        for _ in range(3):
            await asyncio.sleep(0)
        assert 2 in woke

    _run(_test())
