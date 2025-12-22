#!/usr/bin/env python3
"""
Simple up-counter example demonstrating RTL modeling features.

This example shows:
- Input/output port declarations using bit types
- Synchronous process with clock and reset
- Deferred assignment semantics
"""

import zuspec.dataclasses as zdc


@zdc.dataclass
class Counter(zdc.Component):
    """A simple up-counter with synchronous reset"""
    
    # Input ports
    clock : zdc.bit = zdc.input()
    reset : zdc.bit = zdc.input()
    
    # Output ports
    count : zdc.u32 = zdc.output()
    
    @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
    def _count_proc(self):
        """Synchronous counter process
        
        This process executes on positive edge of clock or reset.
        When reset is high, the counter is cleared.
        Otherwise, the counter increments by 1.
        
        Note: Assignments are deferred - the new value takes effect
        after the method completes but before the next evaluation.
        """
        if self.reset:
            self.count = 0
        else:
            # Read old value, increment, write new value
            # Both prints would show same value due to deferred assignment
            self.count = self.count + 1


if __name__ == "__main__":
    print("Counter RTL Example")
    print("=" * 50)
    print()
    print("This example defines a simple 32-bit up-counter with:")
    print("- clock input port (1 bit)")
    print("- reset input port (1 bit)")
    print("- count output port (32 bits)")
    print()
    print("The counter uses a @sync process that:")
    print("- Resets count to 0 when reset is high")
    print("- Increments count by 1 on each clock edge")
    print()
    print("Note: This example shows the API definition.")
    print("Execution engine implementation is planned for future phases.")
