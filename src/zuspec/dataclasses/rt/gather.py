"""zdc.gather — run multiple component method coroutines under a single sim loop."""
from __future__ import annotations

import asyncio
from typing import Any


async def gather(comp, *coros) -> list[Any]:
    """Run coroutines concurrently under a shared simulation time advance loop.

    When called from outside simulation (depth == 0) this function owns the
    sim loop and drives time forward until **all** coroutines complete —
    equivalent to how a single top-level method call works, but for N
    concurrent operations.

    When called from inside simulation (depth > 0) it falls back to a plain
    ``asyncio.gather``.

    Parameters
    ----------
    comp:
        Any ``zdc.Component`` instance that shares the timebase.  Used to
        locate the root component and the timebase.
    *coros:
        Coroutines to run (typically wrapped component method calls such as
        ``bench.dut.transfer(...)``).

    Returns
    -------
    list
        Results in the same order as the input coroutines.

    Example
    -------
    ::

        ctrl0, ctrl1 = await zdc.gather(
            bench.dut,
            bench.dut.transfer(0, src=0x1000, dst=0x2000, length=4),
            bench.dut.transfer(1, src=0x3000, dst=0x4000, length=4),
        )
    """
    timebase = comp._impl.timebase()

    if timebase is None or timebase._execution_depth > 0:
        # Already inside simulation — plain asyncio gather works fine.
        return list(await asyncio.gather(*coros))

    # Top-level entry: we own the sim loop.
    root = comp
    while root._impl.parent is not None:
        root = root._impl.parent

    # Pre-increment depth BEFORE creating tasks so that when each wrapped
    # method runs it sees depth > 0 and takes the "nested" path, using
    # tb.wait() for timing instead of trying to start its own sim loop.
    timebase._execution_depth += 1
    timebase._running = True
    root._impl.start_all_processes(root)

    tasks = [asyncio.create_task(c) for c in coros]

    try:
        while not all(t.done() for t in tasks):
            if timebase._event_queue:
                timebase.advance()
            await asyncio.sleep(0)

        # Propagate any exceptions (mirrors asyncio.gather default behaviour).
        return [t.result() for t in tasks]
    finally:
        timebase._execution_depth -= 1
        timebase._running = False
