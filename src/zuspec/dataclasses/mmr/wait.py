"""zdc.wait_until(*regs, pred) — cross-register async wait."""
from __future__ import annotations

import asyncio
from typing import Callable


async def wait_until(*args) -> None:
    """Suspend until *pred* over the listed registers is satisfied.

    Parameters
    ----------
    *regs : RegisterRT
        One or more register instances to observe.  At least one is required.
    pred : Callable
        The last positional argument.  Receives the register objects in the
        same order as *regs* (not snapshots).  Attribute access on the passed
        objects returns the *current* live field value.

    The coroutine:

    1. Evaluates ``pred(*regs)`` immediately.  If already true, returns
       without suspending.
    2. Otherwise, registers a one-shot callback on every register's
       ``_change`` event and suspends.
    3. On any field change in any watched register, re-evaluates the
       predicate.  If still false, repeats from step 2.

    Single-register shorthand::

        await zdc.wait_until(self.regs.STATUS, lambda s: s.DONE == 1)

    Multi-register form::

        await zdc.wait_until(
            self.regs.CTRL, self.regs.STATUS,
            lambda ctrl, status: ctrl.START == 1 and status.BUSY == 0,
        )

    Notes
    -----
    * Only ``@zdc.proc`` coroutines may call this function; calling it from
      synchronous code raises ``RuntimeError`` (no event loop).
    * The predicate is re-checked from scratch on every wake — it does not
      have to be edge-triggered.
    * Cancellation is safe: the one-shot callback is cleaned up in the
      ``finally`` block even if the coroutine is cancelled.
    """
    if len(args) < 2:
        raise TypeError("wait_until requires at least one register and a predicate")
    regs = args[:-1]
    pred: Callable = args[-1]

    while not pred(*regs):
        events = []
        originals = []
        wake = asyncio.Event()

        def _make_one_shot(reg, orig):
            def _one_shot():
                orig()
                if not wake.is_set():
                    wake.set()
            return _one_shot

        for reg in regs:
            orig = reg._change.set
            originals.append((reg, orig))
            reg._change.set = _make_one_shot(reg, orig)  # type: ignore[method-assign]

        try:
            await wake.wait()
        finally:
            for reg, orig in originals:
                reg._change.set = orig  # type: ignore[method-assign]
