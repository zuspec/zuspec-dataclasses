"""Tier 1 tests for zdc.spawn() and SpawnHandle (Phase 1/2)."""
import asyncio
import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Basic spawn behavior
# ---------------------------------------------------------------------------

class TestSpawnBasic:
    def test_spawned_coro_runs_concurrently(self):
        async def run():
            log = []

            async def work():
                log.append("start")
                await asyncio.sleep(0)
                log.append("end")

            handle = zdc.spawn(work())
            log.append("after_spawn")
            await asyncio.sleep(0)   # yield to let the spawned task run
            await asyncio.sleep(0)
            assert "start" in log
            assert "end" in log
            assert log[0] == "after_spawn"

        asyncio.run(run())

    def test_spawn_does_not_suspend_caller(self):
        async def run():
            log = []

            async def slow():
                await asyncio.sleep(0.001)
                log.append("slow done")

            log.append("before")
            zdc.spawn(slow())
            log.append("after")
            # at this point, "slow done" is NOT yet in the log
            assert log == ["before", "after"]

        asyncio.run(run())


# ---------------------------------------------------------------------------
# SpawnHandle.join()
# ---------------------------------------------------------------------------

class TestSpawnJoin:
    def test_join_waits_for_completion(self):
        async def run():
            result = []

            async def work():
                await asyncio.sleep(0)
                result.append(42)

            handle = zdc.spawn(work())
            await handle.join()
            assert result == [42]

        asyncio.run(run())


# ---------------------------------------------------------------------------
# SpawnHandle.cancel()
# ---------------------------------------------------------------------------

class TestSpawnCancel:
    def test_cancel_terminates_task(self):
        async def run():
            completed = []

            async def work():
                try:
                    await asyncio.sleep(10)
                    completed.append("finished")
                except asyncio.CancelledError:
                    completed.append("cancelled")
                    raise

            handle = zdc.spawn(work())
            await asyncio.sleep(0)   # let it start
            await handle.cancel()
            assert "cancelled" in completed
            assert "finished" not in completed

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Integration: spawn + Completion
# ---------------------------------------------------------------------------

class TestSpawnWithCompletion:
    def test_spawn_sets_completion(self):
        """Spawned coroutine sets a Completion; caller awaits it."""
        async def run():
            done = zdc.Completion[zdc.u32]()

            async def handler(token):
                await asyncio.sleep(0)
                token.set(7)

            zdc.spawn(handler(done))
            result = await done
            assert result == 7

        asyncio.run(run())
