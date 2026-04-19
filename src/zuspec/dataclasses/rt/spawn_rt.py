"""``spawn_rt`` / ``SpawnHandleRT`` — asyncio.create_task-backed spawn."""
from __future__ import annotations

import asyncio
from typing import Coroutine


class SpawnHandleRT:
    """Handle returned by ``spawn_rt()`` during behavioral simulation."""

    def __init__(self, task: asyncio.Task):
        self._task = task

    async def cancel(self) -> None:
        """Request cancellation and wait for the task to stop."""
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass

    async def join(self) -> None:
        """Wait for the spawned task to complete."""
        try:
            await self._task
        except Exception:
            pass

    def __repr__(self):
        return f"SpawnHandleRT(done={self._task.done()})"


def spawn_rt(coro: Coroutine) -> SpawnHandleRT:
    """Create an asyncio task for ``coro`` and return a ``SpawnHandleRT``."""
    task = asyncio.ensure_future(coro)
    return SpawnHandleRT(task)
