"""CounterBank — N independent counters sharing a clock domain.

Usage::

    @zdc.dataclass
    class MyComp(zdc.Component):
        ch_cnt: zdc.CounterBank = zdc.inst(zdc.CounterBank, COUNT=8)

        @zdc.proc
        async def run(self):
            snap = self.ch_cnt.snapshot_all()
            await self.ch_cnt[0].wait_for(snap[0] + 100)
"""
from __future__ import annotations

import dataclasses as dc
from typing import List, Tuple

from .types import SyncComponent
from .counter import Counter
from .decorators import dataclass as _zdcdc, const


@_zdcdc
class CounterBank(SyncComponent):
    """``COUNT`` independent counters sharing a clock domain.

    Counters are accessed by index via ``bank[i]``.  All counters share the
    same clock domain (the bank's ``clock_domain`` class attribute).

    Parameters
    ----------
    COUNT:
        Number of counters.  Defaults to 4.
    WIDTH:
        Bit width of each counter (``modulus == 2**WIDTH``).  Defaults to 32.
    """

    COUNT: int = const(default=4)
    WIDTH: int = const(default=32)

    # Lazily populated list of Counter instances (one per slot).
    _counters: List[Counter] = dc.field(
        default_factory=list, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        # Build the counter list eagerly so _counters[i] is always valid.
        # Each Counter is a plain Python object here (not a zdc Component
        # child), sharing our clock domain via class-level attribute injection.
        self._build_counters()

    def _build_counters(self) -> None:
        """Instantiate lightweight Counter wrappers for each slot."""
        counters = []
        for _ in range(self.COUNT):
            c = _BankCounter(bank=self, WIDTH=self.WIDTH)
            counters.append(c)
        object.__setattr__(self, '_counters', counters)

    def __getitem__(self, idx: int) -> Counter:
        """Return the counter at position *idx*.

        Raises ``IndexError`` when *idx* is out of range.
        """
        if idx < 0 or idx >= self.COUNT:
            raise IndexError(f"CounterBank index {idx} out of range [0, {self.COUNT})")
        return self._counters[idx]

    def snapshot_all(self) -> Tuple[int, ...]:
        """Atomically capture all counter values at the current cycle.

        Returns a tuple of ``COUNT`` integers.  All values are read from the
        same :meth:`~Counter._current_cycle` so they are consistent.
        """
        return tuple(c.value for c in self._counters)


class _BankCounter(Counter):
    """Internal: a Counter that delegates timebase access to a parent bank.

    The bank is a proper ``Component`` whose ``_impl`` can be used to look
    up the timebase.  ``_BankCounter`` overrides ``_current_cycle`` to read
    the timebase from the bank rather than from its own (unset) ``_impl``.
    """

    def __new__(cls, **kwargs):
        # Bypass Component.__new__ which routes through ObjFactory.
        return object.__new__(cls)

    def __init__(self, *, bank: CounterBank, WIDTH: int = 32) -> None:
        # Bypass @zdc.dataclass machinery — instantiate as a plain object.
        object.__setattr__(self, 'WIDTH', WIDTH)
        object.__setattr__(self, '_origin', 0)
        object.__setattr__(self, '_update_event', None)
        object.__setattr__(self, '_impl', None)
        object.__setattr__(self, '_bank', bank)

    def _period_fs(self) -> int:
        # Walk the bank's component hierarchy to find a clock domain with a period.
        bank = object.__getattribute__(self, '_bank')
        comp = bank
        while comp is not None:
            cd = getattr(type(comp), 'clock_domain', None)
            if cd is not None and cd.period is not None:
                return cd._period_fs()
            try:
                parent = comp._impl._parent if comp._impl is not None else None
            except AttributeError:
                parent = None
            comp = parent
        return 1_000_000  # default: 1 ns

    def _current_cycle(self) -> int:
        bank = object.__getattribute__(self, '_bank')
        try:
            tb = bank._impl.timebase()
        except (RuntimeError, AssertionError, AttributeError):
            tb = None
        if tb is not None:
            period_fs = self._period_fs()
            return tb._current_time // period_fs
        # Fallback to tick() mode: walk parent hierarchy for _cycle_count.
        comp = bank
        while comp is not None:
            cd = getattr(type(comp), 'clock_domain', None)
            if cd is not None:
                return cd._cycle_count
            try:
                parent = comp._impl._parent if comp._impl is not None else None
            except AttributeError:
                parent = None
            comp = parent
        return 0

    async def wait(self, amt) -> None:  # type: ignore[override]
        """Delegate wait() to the parent bank component."""
        bank = object.__getattribute__(self, '_bank')
        await bank.wait(amt)
