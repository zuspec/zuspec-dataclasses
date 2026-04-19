"""``zdc.spawn(coro)`` — start a coroutine without awaiting it.

At simulation time wraps ``asyncio.create_task``.  At synthesis the IR
extractor lowers this to a slot-array FSM driven by the IfProtocol port's
``max_outstanding`` bound.

Usage::

    handle = zdc.spawn(self._load_complete(req, done))
    # ... later, optionally:
    await handle.join()
    # or:
    await handle.cancel()
"""
from __future__ import annotations

from typing import Coroutine, Any


def spawn(coro: Coroutine) -> "SpawnHandle":
    """Start ``coro`` concurrently without suspending the caller.

    Returns a ``SpawnHandle`` that supports ``cancel()`` and ``join()``.

    At synthesis the synthesizer bounds concurrent spawns to the
    ``max_outstanding`` of the IfProtocol port called inside ``coro``.
    """
    from zuspec.dataclasses.rt.spawn_rt import spawn_rt
    return spawn_rt(coro)


class SpawnHandle:
    """Handle returned by ``zdc.spawn()``.

    Supports cooperative cancellation and joining.
    """

    async def cancel(self) -> None:
        """Request cancellation of the spawned coroutine and wait for it to stop.

        Note: cancel() in RTL is not yet supported (deferred).
        """
        raise NotImplementedError

    async def join(self) -> None:
        """Suspend the caller until the spawned coroutine completes."""
        raise NotImplementedError
