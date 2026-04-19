"""``zdc.select(*queues_with_tags)`` — wait on the first non-empty queue.

At simulation time uses ``asyncio.wait`` to race multiple ``queue.get()``
tasks.  At synthesis maps to a priority or round-robin arbiter.

Usage::

    item, tag = await zdc.select(
        (self._load_q, "load"),
        (self._store_q, "store"),
    )
    if tag == "load":
        ...
    else:
        ...

Pass ``priority='round_robin'`` to enable round-robin arbitration::

    item, tag = await zdc.select(
        (self._q0, 0), (self._q1, 1),
        priority='round_robin',
    )
"""
from __future__ import annotations

from typing import Tuple, Any


async def select(*queues_with_tags: Tuple[Any, Any], priority: str = "left_to_right") -> Tuple[Any, Any]:
    """Block until any queue in ``queues_with_tags`` is non-empty.

    Each element of ``queues_with_tags`` is a ``(queue, tag)`` pair.
    Returns ``(item, tag)`` from the first queue that yields an item.

    ``priority`` controls which queue wins when multiple are non-empty:

    * ``'left_to_right'`` (default) — leftmost queue in the argument list wins.
    * ``'round_robin'``             — rotates priority after each selection.
    """
    from zuspec.dataclasses.rt.select_rt import select_rt
    return await select_rt(*queues_with_tags, priority=priority)
