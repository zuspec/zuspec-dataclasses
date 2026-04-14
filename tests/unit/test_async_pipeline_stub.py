"""Phase 1 stub tests — verify the async pipeline DSL is importable and
correctly marks methods without requiring any rt execution.
"""

import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.pipeline_ns import _StageHandle, _Snap, _PipelineNamespace


class TestPipelineDecorator:
    def test_pipeline_decorator_plain(self):
        """@zdc.pipeline (bare form) marks method with _zdc_async_pipeline."""
        @zdc.pipeline
        async def run(self): ...
        assert getattr(run, '_zdc_async_pipeline', False) is True

    def test_pipeline_decorator_with_clock(self):
        """@zdc.pipeline(clock=...) stores the lambda on the method."""
        clk = lambda s: s.clk
        @zdc.pipeline(clock=clk)
        async def run(self): ...
        assert run._zdc_async_pipeline is True
        assert run._zdc_pipeline_clock is clk

    def test_pipeline_decorator_with_reset(self):
        """@zdc.pipeline(reset=...) stores the reset lambda."""
        rst = lambda s: s.rst_n
        @zdc.pipeline(reset=rst)
        async def run(self): ...
        assert run._zdc_pipeline_reset is rst

    def test_pipeline_decorator_clock_and_reset(self):
        """Both clock and reset lambdas are stored."""
        clk = lambda s: s.clock
        rst = lambda s: s.reset
        @zdc.pipeline(clock=clk, reset=rst)
        async def run(self): ...
        assert run._zdc_pipeline_clock is clk
        assert run._zdc_pipeline_reset is rst

    def test_pipeline_decorator_no_clock_default_none(self):
        """When no clock given, _zdc_pipeline_clock is None."""
        @zdc.pipeline
        async def run(self): ...
        assert run._zdc_pipeline_clock is None
        assert run._zdc_pipeline_reset is None

    def test_pipeline_decorator_with_clock_domain(self):
        """@zdc.pipeline(clock_domain=...) stores the lambda on the method."""
        cd = lambda s: s.clk
        @zdc.pipeline(clock_domain=cd)
        async def run(self): ...
        assert run._zdc_pipeline_clock_domain is cd

    def test_pipeline_decorator_clock_domain_default_none(self):
        """When no clock_domain given, _zdc_pipeline_clock_domain is None."""
        @zdc.pipeline
        async def run(self): ...
        assert getattr(run, '_zdc_pipeline_clock_domain', None) is None


class TestStageHandle:
    def test_stage_returns_handle(self):
        """zdc.pipeline.stage() returns a _StageHandle outside rt."""
        handle = zdc.pipeline.stage()
        assert isinstance(handle, _StageHandle)

    def test_stage_with_cycles(self):
        """stage(cycles=2) stores the cycles count."""
        handle = zdc.pipeline.stage(cycles=2)
        assert isinstance(handle, _StageHandle)
        assert handle._cycles == 2

    def test_stage_async_context_manager(self):
        """_StageHandle works as async context manager."""
        async def _run():
            async with zdc.pipeline.stage() as s:
                assert s is not None
                assert isinstance(s, _StageHandle)
        asyncio.run(_run())

    def test_stage_valid_default_true(self):
        """_StageHandle.valid returns True by default."""
        h = zdc.pipeline.stage()
        assert h.valid is True

    def test_stage_cycle_default_zero(self):
        """_StageHandle.cycle returns 0 by default."""
        h = zdc.pipeline.stage()
        assert h.cycle == 0

    def test_stage_stall_is_async(self):
        """_StageHandle.stall() is awaitable."""
        async def _run():
            h = zdc.pipeline.stage()
            async with h as s:
                await s.stall(1)
        asyncio.run(_run())

    def test_stage_bubble_is_async(self):
        """_StageHandle.bubble() is awaitable."""
        async def _run():
            h = zdc.pipeline.stage()
            async with h as s:
                await s.bubble()
        asyncio.run(_run())


class TestPipelineResource:
    def test_resource_subscript_returns_proxy(self):
        """PipelineResource[addr] returns a _ResourceProxy."""
        from zuspec.dataclasses.pipeline_resource import _ResourceProxy
        rf = zdc.pipeline.resource(32)
        proxy = rf[7]
        assert isinstance(proxy, _ResourceProxy)
        assert proxy.addr == 7
        assert proxy.resource is rf

    def test_resource_default_queue_lock(self):
        """When no lock given, defaults to QueueLock."""
        rf = zdc.pipeline.resource(32)
        assert isinstance(rf.lock, zdc.QueueLock)

    def test_resource_with_bypass_lock(self):
        """resource(size, lock=BypassLock()) stores the lock."""
        bl = zdc.BypassLock(bypass_latency=2)
        rf = zdc.pipeline.resource(32, lock=bl)
        assert rf.lock is bl

    def test_resource_size(self):
        """PipelineResource.size matches the constructor argument."""
        rf = zdc.pipeline.resource(64)
        assert rf.size == 64


class TestSnap:
    def test_snap_present_attr(self):
        """_Snap returns stored values by attribute."""
        s = _Snap({"x": 42, "y": "hello"})
        assert s.x == 42
        assert s.y == "hello"

    def test_snap_missing_attr_returns_none(self):
        """_Snap returns None for unknown attributes."""
        s = _Snap({"x": 42})
        assert s.missing is None
        assert s.also_missing is None

    def test_snap_empty(self):
        """_Snap with empty dict returns None for any attr."""
        s = _Snap({})
        assert s.whatever is None


class TestHazardLocks:
    def test_queue_lock_instantiation(self):
        assert isinstance(zdc.QueueLock(), zdc.HazardLock)

    def test_bypass_lock_instantiation(self):
        bl = zdc.BypassLock(bypass_latency=2)
        assert isinstance(bl, zdc.HazardLock)
        assert bl.bypass_latency == 2

    def test_rename_lock_instantiation(self):
        rl = zdc.RenameLock(phys_regs=64)
        assert isinstance(rl, zdc.HazardLock)
        assert rl.phys_regs == 64


class TestPipelineSingleton:
    def test_pipeline_is_namespace_instance(self):
        assert isinstance(zdc.pipeline, _PipelineNamespace)

    def test_current_cycle_outside_rt(self):
        """current_cycle() returns 0 outside rt execution."""
        assert zdc.pipeline.current_cycle() == 0

    def test_find_returns_none_outside_rt(self):
        """find() returns None outside rt execution."""
        result = zdc.pipeline.find(lambda s: True)
        assert result is None
