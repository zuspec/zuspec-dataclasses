"""Tests for @process decorator functionality."""
import asyncio
import pytest
import zuspec.dataclasses as zdc


class TestProcess:
    """Tests for process decorator and simulation timebase."""

    def test_single_process(self):
        """Test that a single @process method runs correctly."""
        @zdc.dataclass
        class SimpleC(zdc.Component):
            counter: int = 0
            
            @zdc.process
            async def _run(self):
                for i in range(3):
                    self.counter = i + 1
                    await self.wait(zdc.Time.ns(1))

        c = SimpleC()
        asyncio.run(c.wait(zdc.Time.ns(10)))
        assert c.counter == 3

    def test_multiple_processes(self):
        """Test that multiple @process methods run concurrently."""
        @zdc.dataclass
        class MultiProcC(zdc.Component):
            counter_a: int = 0
            counter_b: int = 0
            
            @zdc.process
            async def proc_a(self):
                for i in range(3):
                    self.counter_a += 1
                    await self.wait(zdc.Time.ns(2))

            @zdc.process
            async def proc_b(self):
                for i in range(5):
                    self.counter_b += 1
                    await self.wait(zdc.Time.ns(1))

        c = MultiProcC()
        asyncio.run(c.wait(zdc.Time.ns(10)))
        assert c.counter_a == 3
        assert c.counter_b == 5

    def test_nested_component_processes(self):
        """Test that processes in nested components run."""
        @zdc.dataclass
        class ChildC(zdc.Component):
            value: int = 0
            
            @zdc.process
            async def _run(self):
                for i in range(4):
                    self.value = i + 1
                    await self.wait(zdc.Time.ns(1))

        @zdc.dataclass
        class ParentC(zdc.Component):
            child: ChildC = zdc.field()
            parent_value: int = 0
            
            @zdc.process
            async def _run(self):
                for i in range(2):
                    self.parent_value = i + 1
                    await self.wait(zdc.Time.ns(2))

        c = ParentC()
        asyncio.run(c.wait(zdc.Time.ns(10)))
        assert c.child.value == 4
        assert c.parent_value == 2

    def test_process_time_units(self):
        """Test different time units work correctly."""
        @zdc.dataclass  
        class TimeUnitC(zdc.Component):
            ns_count: int = 0
            us_count: int = 0
            
            @zdc.process
            async def ns_proc(self):
                for _ in range(10):
                    self.ns_count += 1
                    await self.wait(zdc.Time.ns(100))

            @zdc.process
            async def us_proc(self):
                self.us_count += 1
                await self.wait(zdc.Time.us(1))

        c = TimeUnitC()
        asyncio.run(c.wait(zdc.Time.us(1)))
        assert c.ns_count == 10  # 10 * 100ns = 1us
        assert c.us_count == 1

    def test_process_no_wait(self):
        """Test process that completes without waiting."""
        @zdc.dataclass
        class NoWaitC(zdc.Component):
            done: bool = False
            
            @zdc.process
            async def _run(self):
                self.done = True

        c = NoWaitC()
        asyncio.run(c.wait(zdc.Time.ns(1)))
        assert c.done is True
