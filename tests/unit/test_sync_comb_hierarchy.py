"""Test sync/comb processes in hierarchical components.

This test demonstrates the issue where child component outputs aren't 
visible to parent after sync processes run.
"""
import zuspec.dataclasses as zdc


def test_child_sync_parent_comb():
    """Test that child sync process updates are visible to parent comb process."""
    
    @zdc.dataclass
    class Counter(zdc.Component):
        """Child component with sync process that increments a counter."""
        clk: zdc.bit = zdc.input()
        count_out: zdc.bit32 = zdc.output()
        
        # Internal state
        count: zdc.bit32 = zdc.field(default=0)
        
        @zdc.sync(clock=lambda self: self.clk, reset=None)
        def _increment(self):
            """Increment counter on clock edge."""
            self.count = (self.count + 1) & 0xFFFFFFFF
        
        @zdc.comb
        def _output(self):
            """Output the count."""
            self.count_out = self.count
    
    @zdc.dataclass
    class Parent(zdc.Component):
        """Parent component that reads child output."""
        clk: zdc.bit = zdc.input()
        value: zdc.bit32 = zdc.output()
        
        child: Counter = zdc.field()
        
        def __bind__(self):
            return {
                self.child.clk: self.clk
            }
        
        @zdc.comb
        def _passthrough(self):
            """Pass through child output."""
            self.value = self.child.count_out
    
    # Create parent (child auto-constructed)
    parent = Parent()
    
    print(f"Initial: child.count={parent.child.count}, child.count_out={parent.child.count_out}, parent.value={parent.value}")
    
    # Clock once
    parent.clk = 1
    print(f"After clk=1: child.count={parent.child.count}, child.count_out={parent.child.count_out}, parent.value={parent.value}")
    
    parent.clk = 0
    print(f"After clk=0: child.count={parent.child.count}, child.count_out={parent.child.count_out}, parent.value={parent.value}")
    
    # Expected: child.count=1, child.count_out=1, parent.value=1
    assert parent.child.count == 1, f"Expected child.count=1, got {parent.child.count}"
    assert parent.child.count_out == 1, f"Expected child.count_out=1, got {parent.child.count_out}"
    assert parent.value == 1, f"Expected parent.value=1, got {parent.value}"
    
    # Clock again
    parent.clk = 1
    parent.clk = 0
    print(f"After 2nd cycle: child.count={parent.child.count}, child.count_out={parent.child.count_out}, parent.value={parent.value}")
    
    assert parent.child.count == 2
    assert parent.child.count_out == 2
    assert parent.value == 2


def test_simple_sync_comb():
    """Simpler test: single component with sync updating state and comb outputting."""
    
    @zdc.dataclass
    class Counter(zdc.Component):
        clk: zdc.bit = zdc.input()
        count_out: zdc.bit32 = zdc.output()
        
        count: zdc.bit32 = zdc.field(default=0)
        
        @zdc.sync(clock=lambda self: self.clk, reset=None)
        def _increment(self):
            self.count = (self.count + 1) & 0xFFFFFFFF
        
        @zdc.comb
        def _output(self):
            self.count_out = self.count
    
    counter = Counter()
    
    print(f"\nSimple test - Initial: count={counter.count}, count_out={counter.count_out}")
    
    counter.clk = 1
    print(f"After clk=1: count={counter.count}, count_out={counter.count_out}")
    
    assert counter.count == 1, f"Expected count=1, got {counter.count}"
    assert counter.count_out == 1, f"Expected count_out=1, got {counter.count_out}"
    
    counter.clk = 0
    counter.clk = 1
    print(f"After 2nd edge: count={counter.count}, count_out={counter.count_out}")
    
    assert counter.count == 2
    assert counter.count_out == 2
