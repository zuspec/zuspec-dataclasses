"""WatchdogCounter — fires a timeout callback if not kicked in time.

Usage::

    @zdc.dataclass
    class MyComp(zdc.Component):
        wdog: zdc.WatchdogCounter = zdc.inst(zdc.WatchdogCounter, TIMEOUT=1000)

        @zdc.proc
        async def monitor(self):
            self.wdog.arm()
            # ... periodically call self.wdog.kick() ...
"""
from __future__ import annotations

import dataclasses as dc
from typing import Optional

from .counter import Counter
from .decorators import dataclass as _zdcdc, const


@_zdcdc
class WatchdogCounter(Counter):
    """Counter that fires :meth:`on_timeout` if not kicked within ``TIMEOUT`` cycles.

    Arm the watchdog with :meth:`arm`, keep it alive by calling :meth:`kick`
    before the timeout expires, and stop it with :meth:`disarm`.

    Parameters
    ----------
    TIMEOUT:
        Default number of cycles before :meth:`on_timeout` is called.
        Can be overridden per-arm by passing *cycles* to :meth:`arm`.
    """

    TIMEOUT: int = const(default=1000)

    # Deadline (absolute cycle count) for the current arm window; None when disarmed.
    _deadline: Optional[int] = dc.field(default=None, init=False, repr=False, compare=False)
    # Handle to the spawned timeout coroutine so we can cancel it on kick/disarm.
    _handle = dc.field(default=None, init=False, repr=False, compare=False)

    # ── Public control ──────────────────────────────────────────────────────

    def arm(self, cycles: Optional[int] = None) -> None:
        """Start (or restart) the watchdog.

        Parameters
        ----------
        cycles:
            Timeout window in cycles.  Uses ``TIMEOUT`` when ``None``.
        """
        window = int(cycles) if cycles is not None else self.TIMEOUT
        self._deadline = self._current_cycle() + window
        self._restart_timeout_task(window)

    def kick(self) -> None:
        """Reset the timeout window from now; keeps the watchdog armed."""
        if self._deadline is None:
            return  # not armed — silently ignore
        self.arm()

    def disarm(self) -> None:
        """Stop the watchdog without firing the callback."""
        self._deadline = None
        self._cancel_timeout_task()

    # ── Overridable callback ────────────────────────────────────────────────

    async def on_timeout(self) -> None:
        """Called when the watchdog expires.

        Override in a subclass or bind a callback to react to expiry.
        Default implementation is a no-op.
        """

    # ── Internal ────────────────────────────────────────────────────────────

    def _cancel_timeout_task(self) -> None:
        h = object.__getattribute__(self, '_handle')
        if h is not None and hasattr(h, 'cancel'):
            import asyncio
            # SpawnHandle doesn't expose direct cancel; cancel the underlying task.
            if hasattr(h, '_task') and h._task is not None:
                h._task.cancel()
            elif isinstance(h, asyncio.Task):
                h.cancel()
        object.__setattr__(self, '_handle', None)

    def _restart_timeout_task(self, window: int) -> None:
        self._cancel_timeout_task()
        import asyncio
        task = asyncio.create_task(self._timeout_coro(window))
        object.__setattr__(self, '_handle', task)

    async def _timeout_coro(self, window: int) -> None:
        from .types import Time, TimeUnit
        await self.wait(Time(TimeUnit.FS, window * self._period_fs()))
        # Only fire if still armed (kick/disarm may have changed _deadline).
        if self._deadline is not None:
            await self.on_timeout()
