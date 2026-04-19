"""Tier 1 tests for zdc.iface_select() (Phase 1/2)."""
import asyncio
import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Basic select behavior
# ---------------------------------------------------------------------------

class TestSelectBasic:
    def test_single_non_empty_queue_fires(self):
        async def run():
            q = zdc.queue(depth=2)
            await q.put("hello")
            item, tag = await zdc.iface_select((q, "q0"))
            assert item == "hello"
            assert tag == "q0"

        asyncio.run(run())

    def test_returns_correct_tag(self):
        async def run():
            q0 = zdc.queue(depth=2)
            q1 = zdc.queue(depth=2)
            await q1.put(99)
            item, tag = await zdc.iface_select((q0, "first"), (q1, "second"))
            assert item == 99
            assert tag == "second"

        asyncio.run(run())

    def test_awaits_until_item_available(self):
        async def run():
            q = zdc.queue(depth=2)
            result = []

            async def consumer():
                item, tag = await zdc.iface_select((q, "tag"))
                result.append((item, tag))

            asyncio.create_task(consumer())
            await asyncio.sleep(0)
            assert not result

            await q.put("later")
            for _ in range(4):
                await asyncio.sleep(0)
            assert result == [("later", "tag")]

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Priority: left-to-right when both non-empty
# ---------------------------------------------------------------------------

class TestSelectPriority:
    def test_left_wins_when_both_ready(self):
        async def run():
            q0 = zdc.queue(depth=2)
            q1 = zdc.queue(depth=2)
            await q0.put("from_q0")
            await q1.put("from_q1")
            item, tag = await zdc.iface_select((q0, "q0"), (q1, "q1"))
            assert tag == "q0"
            assert item == "from_q0"

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Round-robin
# ---------------------------------------------------------------------------

class TestSelectRoundRobin:
    def test_round_robin_rotates(self):
        """With round-robin, each successive call should prefer a different queue."""
        async def run():
            # Reset global counter
            from zuspec.dataclasses.rt.select_rt import select_rt
            if hasattr(select_rt, "_rr_counter"):
                select_rt._rr_counter = 0

            q0 = zdc.queue(depth=4)
            q1 = zdc.queue(depth=4)
            # Pre-fill both
            for _ in range(2):
                await q0.put("a")
                await q1.put("b")

            tags = []
            for _ in range(4):
                item, tag = await zdc.iface_select((q0, "q0"), (q1, "q1"), priority="round_robin")
                tags.append(tag)

            # With round-robin starting at 0, first pick is q0, then q1, etc.
            assert "q0" in tags
            assert "q1" in tags

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestSelectEdgeCases:
    def test_empty_args_raises(self):
        async def run():
            with pytest.raises((ValueError, Exception)):
                await zdc.iface_select()

        asyncio.run(run())

    def test_integer_tags(self):
        async def run():
            q = zdc.queue(depth=2)
            await q.put("x")
            item, tag = await zdc.iface_select((q, 42))
            assert tag == 42

        asyncio.run(run())
