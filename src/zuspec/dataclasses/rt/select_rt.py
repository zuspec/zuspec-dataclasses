"""``select_rt`` — asyncio-based select for behavioral simulation.

Races multiple ``queue.get()`` coroutines and returns the result from the
first queue that produces an item.
"""
from __future__ import annotations

import asyncio
from typing import Tuple, Any


async def select_rt(*queues_with_tags, priority: str = "left_to_right") -> Tuple[Any, Any]:
    """Wait for the first non-empty queue; return ``(item, tag)``.

    ``queues_with_tags`` is a sequence of ``(queue, tag)`` pairs.

    ``priority``:
    * ``'left_to_right'`` — leftmost argument wins on a tie.
    * ``'round_robin'``   — rotates the winning queue across calls.
      The rotation state is stored on the function object itself (per
      ``select_rt`` call-site).  For a per-select-instance counter,
      use a ``SelectContext`` object (future enhancement).
    """
    if not queues_with_tags:
        raise ValueError("select() requires at least one (queue, tag) pair")

    queues = [pair[0] for pair in queues_with_tags]
    tags   = [pair[1] for pair in queues_with_tags]

    # Determine poll order based on priority policy
    if priority == "round_robin":
        if not hasattr(select_rt, "_rr_counter"):
            select_rt._rr_counter = 0  # type: ignore[attr-defined]
        start = select_rt._rr_counter % len(queues)  # type: ignore[attr-defined]
        order = list(range(start, len(queues))) + list(range(0, start))
    else:
        order = list(range(len(queues)))

    # Create one task per queue
    loop = asyncio.get_event_loop()
    pending_tasks: list[asyncio.Task] = []
    idx_map: dict[asyncio.Task, int] = {}
    for i in order:
        t = loop.create_task(queues[i].get())
        pending_tasks.append(t)
        idx_map[t] = i

    done_set, pending_set = await asyncio.wait(
        pending_tasks, return_when=asyncio.FIRST_COMPLETED
    )

    # Cancel tasks still waiting (blocked on empty queues).
    for t in pending_set:
        t.cancel()
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass

    # Pick the winning task — when multiple finish simultaneously, prefer the
    # one with the lowest original index (left-to-right / round-robin order).
    winner = min(done_set, key=lambda t: order.index(idx_map[t]))
    winning_idx = idx_map[winner]
    item = winner.result()

    # Put back items consumed by losing tasks that also completed.
    # This can happen when multiple queues are non-empty simultaneously.
    for t in done_set:
        if t is not winner:
            try:
                lost_item = t.result()
                queues[idx_map[t]]._q.put_nowait(lost_item)
            except Exception:
                pass

    if priority == "round_robin":
        select_rt._rr_counter = (winning_idx + 1) % len(queues)  # type: ignore[attr-defined]

    return item, tags[winning_idx]
