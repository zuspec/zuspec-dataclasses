"""Test Execution Engine (Phase 2B/2C)"""
import asyncio
import pytest
import zuspec.dataclasses as zdc


def test_simple_counter():
    """Test a simple counter with sync process"""
    
    @zdc.dataclass
    class Counter(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        count : zdc.bit32 = zdc.output()
        
        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _count_proc(self):
            if self.reset:
                self.count = 0
            else:
                self.count = self.count + 1
    
    counter = Counter()

    async def wait(amt : int):
        nonlocal counter

        for _ in range(amt):
            counter.clock = 1
            await counter.wait(zdc.Time.ns(5))
            counter.clock = 0
            await counter.wait(zdc.Time.ns(5))


    async def run():
        nonlocal counter
        # Initial state
        assert counter.count == 0
    
        # Reset
        counter.reset = 1
        counter.clock = 0
        await counter.wait(zdc.Time.ns(5))
        await wait(1)
        assert counter.count == 0

        await wait(20) 

        assert counter.count == 0
    
        # Release reset and count
        counter.reset = 0
        await wait(10) 
        assert counter.count == 10

        await wait(10) 
        assert counter.count == 20

    asyncio.run(run())    


def test_deferred_assignment_semantics():
    """Verify that sync processes read old values and write new values"""
    
    @zdc.dataclass
    class DeferredTest(zdc.Component):
        clock : zdc.bit = zdc.input()
        value : zdc.bit8 = zdc.field()
        old_value : zdc.bit8 = zdc.field()
        
        @zdc.sync(clock=lambda s: s.clock)
        def _proc(self):
            self.old_value = self.value
            self.value = self.value + 1
    
    comp = DeferredTest()
    
    # Set initial value
    comp.value = 5
    
    async def run():
        nonlocal comp
        
        # After one clock edge, old_value should have captured the old value (5)
        # and value should be incremented (6)
        comp.clock = 1
        await comp.wait(zdc.Time.ns(5))
        comp.clock = 0
        await comp.wait(zdc.Time.ns(5))
        
        assert comp.old_value == 5
        assert comp.value == 6
    
    asyncio.run(run())


def test_simple_comb_process():
    """Test a simple combinational process"""
    
    @zdc.dataclass
    class XorGate(zdc.Component):
        a : zdc.bit8 = zdc.input()
        b : zdc.bit8 = zdc.input()
        out : zdc.bit8 = zdc.output()
        
        @zdc.comb
        def _xor_calc(self):
            self.out = self.a ^ self.b
    
    gate = XorGate()
    
    # Set inputs - comb process evaluates automatically
    gate.a = 5
    gate.b = 3
    
    assert gate.out == (5 ^ 3)


def test_comb_auto_evaluation():
    """Test that comb processes re-evaluate when inputs change"""
    
    @zdc.dataclass
    class AddGate(zdc.Component):
        a : zdc.bit8 = zdc.input()
        b : zdc.bit8 = zdc.input()
        sum : zdc.bit8 = zdc.output()
        
        @zdc.comb
        def _add(self):
            self.sum = self.a + self.b
    
    gate = AddGate()
    
    # Initial state
    assert gate.sum == 0
    
    # Change input a - should trigger re-evaluation
    gate.a = 10
    assert gate.sum == 10
    
    # Change input b - should trigger re-evaluation
    gate.b = 5
    assert gate.sum == 15


def test_sync_and_comb_together():
    """Test component with both sync and comb processes"""
    
    @zdc.dataclass
    class Pipeline(zdc.Component):
        clock : zdc.bit = zdc.input()
        a : zdc.bit8 = zdc.input()
        b : zdc.bit8 = zdc.input()
        result : zdc.bit8 = zdc.output()
        
        _sum : zdc.bit8 = zdc.field()
        
        @zdc.comb
        def _add(self):
            self._sum = self.a + self.b
        
        @zdc.sync(clock=lambda s: s.clock)
        def _register(self):
            self.result = self._sum
    
    pipeline = Pipeline()
    
    async def run():
        nonlocal pipeline
        
        # Set inputs - comb calculates sum immediately
        pipeline.a = 10
        pipeline.b = 20
        
        assert pipeline._sum == 30
        
        # Result is not updated yet (sync process hasn't run)
        assert pipeline.result == 0
        
        # Clock edge captures the sum
        pipeline.clock = 1
        await pipeline.wait(zdc.Time.ns(5))
        pipeline.clock = 0
        await pipeline.wait(zdc.Time.ns(5))
        
        assert pipeline.result == 30
    
    asyncio.run(run())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
