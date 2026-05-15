"""Abstract counter — lazy, time-based cycle counter.

Simulation: value is derived lazily from elapsed clock-domain cycles;
no per-cycle callback overhead.

Usage::

    @zdc.dataclass
    class MyComp(zdc.Component):
        free_cnt: zdc.Counter = zdc.inst(zdc.Counter)

        @zdc.proc
        async def run(self):
            snap = self.free_cnt.snapshot()
            await self.free_cnt.wait_for(snap + 256)
"""
from __future__ import annotations

import asyncio
import dataclasses as dc
from typing import Callable, Optional

from .types import SyncComponent, Component
from .decorators import dataclass as _zdcdc, const
from .rt.timebase import Timebase


@_zdcdc
class Counter(SyncComponent):
    """Efficient abstract cycle counter.

    Simulation: :attr:`value` is computed lazily as
    ``(elapsed_cycles - _origin) % modulus`` — no per-cycle interrupt.
    RTL: lowers to a registered accumulator + comparator (handled by
    ``zuspec-be-sw`` / ``zuspec-synth``).

    Parameters
    ----------
    WIDTH:
        Bit width of the counter.  ``modulus == 2**WIDTH``.  Defaults to 32.
    """

    WIDTH: int = const(default=32)

    # _origin and _update_event are NOT dataclass fields — the zdc factory
    # replaces init=False fields with default=None.  We initialise them in
    # __post_init__ via object.__setattr__ so the dataclass machinery and
    # _signal_values flush never touch them.

    def __post_init__(self) -> None:
        super().__post_init__()
        # Initialise mutable state that zdc must not manage.
        if not hasattr(self, '_origin'):
            object.__setattr__(self, '_origin', 0)
        if not hasattr(self, '_update_event'):
            object.__setattr__(self, '_update_event', None)

    # ── Internal helpers ────────────────────────────────────────────────────

    def _period_fs(self) -> int:
        """Clock period in femtoseconds.

        Looks up the most specific clock domain in the component hierarchy that
        has a period set, starting from this Counter and walking up to the root.
        Falls back to 1 ns (1_000_000 fs) when no period is found.
        """
        # Walk the component hierarchy to find a clock domain with a period.
        comp = self
        while comp is not None:
            cd = getattr(type(comp), 'clock_domain', None)
            if cd is not None and cd.period is not None:
                return cd._period_fs()
            # Traverse to parent component.
            try:
                parent = comp._impl._parent if comp._impl is not None else None
            except AttributeError:
                parent = None
            comp = parent
        return 1_000_000  # default: 1 ns

    def _current_cycle(self) -> int:
        """Elapsed cycles since timebase start (or tick() calls in TB mode)."""
        cd = type(self).clock_domain
        # Prefer timebase (pipeline / asyncio.run style):
        try:
            tb = self._impl.timebase()
        except (RuntimeError, AssertionError, AttributeError):
            tb = None
        if tb is not None:
            period_fs = self._period_fs()
            return tb._current_time // period_fs
        # Testbench tick() mode — use _cycle_count on the domain.
        return cd._cycle_count

    def _ensure_update_event(self) -> asyncio.Event:
        """Return (creating if necessary) the asyncio.Event for reset notifications."""
        ev = object.__getattribute__(self, '_update_event')
        if ev is None:
            ev = asyncio.Event()
            object.__setattr__(self, '_update_event', ev)
        return ev

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def modulus(self) -> int:
        """Rollover point: ``2**WIDTH``."""
        return 2 ** self.WIDTH

    @property
    def value(self) -> int:
        """Current counter value (lazy in simulation)."""
        origin = object.__getattribute__(self, '_origin')
        return (self._current_cycle() - origin) % self.modulus

    def snapshot(self) -> int:
        """Alias for :attr:`value`; communicates timestamping intent."""
        return self.value

    def reset(self, v: int = 0) -> None:
        """Set the logical counter value to *v* without stopping simulation.

        ``Counter.value`` will equal *v* immediately after this call.  Any
        coroutines blocked in :meth:`wait_for` (callable variant) will
        recompute their target on the next wake.
        """
        new_origin = self._current_cycle() - (v % self.modulus)
        object.__setattr__(self, '_origin', new_origin)
        # Wake callable wait_for() waiters so they recompute their target.
        ev = object.__getattribute__(self, '_update_event')
        if ev is not None:
            ev.set()
            # Clear on the next iteration so waiters that woke can re-arm.
            asyncio.get_event_loop().call_soon(ev.clear)

    async def wait_for(self, target) -> None:
        """Suspend until the counter reaches *target*.

        *target* may be an ``int`` or a zero-argument callable that returns
        an ``int``.  When a callable is provided the target is re-evaluated
        after every reschedule (e.g. after :meth:`reset` is called).

        Handles rollover transparently.  ``wait_for(v)`` where
        ``v == self.value`` returns immediately.
        """
        if callable(target):
            await self._wait_for_callable(target)
        else:
            await self._wait_for_int(int(target))

    async def _wait_for_int(self, target: int) -> None:
        target = target % self.modulus
        current = self.value
        delta = (target - current) % self.modulus
        if delta == 0:
            return
        period_fs = self._period_fs()
        from .types import Time, TimeUnit
        await self.wait(Time(TimeUnit.FS, delta * period_fs))

    async def _wait_for_callable(self, target_fn: Callable[[], int]) -> None:
        from .types import Time, TimeUnit
        ev = self._ensure_update_event()
        while True:
            target = target_fn() % self.modulus
            current = self.value
            if current == target:
                return
            delta = (target - current) % self.modulus
            period_fs = self._period_fs()

            timer_task = asyncio.create_task(
                self.wait(Time(TimeUnit.FS, delta * period_fs))
            )
            update_task = asyncio.create_task(ev.wait())

            done, pending = await asyncio.wait(
                {timer_task, update_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

            if timer_task in done and target_fn() % self.modulus == target:
                return  # target reached and it hasn't changed

            # reset() fired or target shifted — recompute on next iteration.

    async def wait_ge(self, threshold: int) -> None:
        """Suspend until ``value >= threshold``.

        Handles the case where *threshold* has already been passed in the
        current wrap period by waiting for the next occurrence.
        """
        threshold = threshold % self.modulus
        if self.value >= threshold:
            return
        await self._wait_for_int(threshold)

    async def wait_next(self) -> None:
        """Suspend until the next rollover (``value`` wraps to 0)."""
        current = self.value
        # Wait for the remainder of the current wrap period to reach 0 again.
        # If we're already at 0, wait a full modulus cycles to hit 0 again.
        delta = self.modulus - current if current != 0 else self.modulus
        period_fs = self._period_fs()
        from .types import Time, TimeUnit
        await self.wait(Time(TimeUnit.FS, delta * period_fs))

    def schedule(
        self,
        target: int,
        callback: Callable[[], None],
        *,
        repeat: bool = False,
    ) -> "ScheduleHandle":
        """Register *callback* to fire when the counter reaches *target*.

        Returns a :class:`ScheduleHandle` that supports cancellation and
        rescheduling.

        Parameters
        ----------
        target:
            Counter value at which *callback* fires.
        callback:
            Zero-argument callable invoked when target is reached.
        repeat:
            If ``True`` the schedule fires on every subsequent period at the
            same phase.
        """
        handle = ScheduleHandle(
            counter=self,
            target=int(target) % self.modulus,
            callback=callback,
            repeat=repeat,
        )
        from .spawn import spawn
        spawn(handle._run())
        return handle


class ScheduleHandle:
    """Opaque handle returned by :meth:`Counter.schedule`.

    Provides cooperative cancellation and one-shot rescheduling.
    """

    def __init__(
        self,
        *,
        counter: Counter,
        target: int,
        callback: Callable[[], None],
        repeat: bool = False,
    ) -> None:
        self._counter = counter
        self._target = target
        self._callback = callback
        self._repeat = repeat
        self._cancelled = False
        self._fired = False

    async def _run(self) -> None:
        while True:
            await self._counter.wait_for(self._target)
            if self._cancelled:
                return
            self._callback()
            self._fired = True
            if not self._repeat:
                return
            # Advance exactly one cycle past the target so the next wait_for()
            # sees delta > 0 and waits a full period rather than returning
            # immediately (delta == 0 is the idempotent "already there" case).
            from .types import Time, TimeUnit
            await self._counter.wait(
                Time(TimeUnit.FS, self._counter._period_fs())
            )

    def cancel(self) -> None:
        """Prevent the callback from firing.

        Safe to call even after the callback has already fired or was
        previously cancelled.
        """
        self._cancelled = True

    def reschedule(self, new_target: int) -> None:
        """Cancel the current schedule and register a new one atomically."""
        self.cancel()
        new_target = int(new_target) % self._counter.modulus
        new_handle = self._counter.schedule(
            new_target, self._callback, repeat=self._repeat
        )
        # Proxy the new handle's state back so callers holding this reference
        # see the updated target and fired status.
        self._cancelled = False
        self._target = new_target
        self._fired = new_handle._fired

    @property
    def fired(self) -> bool:
        """``True`` if the callback has fired at least once."""
        return self._fired
