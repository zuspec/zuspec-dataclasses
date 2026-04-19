"""Tier 1 tests for zdc.Completion[T] (Phase 1/2)."""
import asyncio
import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Basic set/await round-trip
# ---------------------------------------------------------------------------

class TestCompletionBasic:
    def test_set_then_await(self):
        async def run():
            done = zdc.Completion[zdc.u32]()
            assert done.is_set is False
            done.set(42)
            result = await done
            assert result == 42
            assert done.is_set is True

        asyncio.run(run())

    def test_await_before_set(self):
        """Await suspends until set() is called from another task."""
        async def run():
            done = zdc.Completion[zdc.u32]()

            async def setter():
                await asyncio.sleep(0)
                done.set(99)

            asyncio.create_task(setter())
            result = await done
            assert result == 99

        asyncio.run(run())

    def test_double_set_raises(self):
        async def run():
            done = zdc.Completion[zdc.u32]()
            done.set(1)
            with pytest.raises(RuntimeError, match="more than once"):
                done.set(2)

        asyncio.run(run())

    def test_is_set_property(self):
        async def run():
            done = zdc.Completion[zdc.u32]()
            assert not done.is_set
            done.set(0)
            assert done.is_set

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Void case (Completion[None])
# ---------------------------------------------------------------------------

class TestCompletionVoid:
    def test_completion_none(self):
        async def run():
            done = zdc.Completion[type(None)]()
            done.set(None)
            result = await done
            assert result is None

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Generic subscript
# ---------------------------------------------------------------------------

class TestCompletionGenericSubscript:
    def test_subscript_returns_alias(self):
        alias = zdc.Completion[zdc.u32]
        # Calling the alias returns a CompletionRT instance
        obj = alias()
        assert hasattr(obj, "set")
        assert hasattr(obj, "is_set")

    def test_repr(self):
        alias = zdc.Completion[zdc.u32]
        assert "Completion" in repr(alias)
