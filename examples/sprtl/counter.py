#!/usr/bin/env python3
"""
Simple counter example demonstrating SPRTL (Synchronous Process RTL) features.

This example shows:
- Input/output port declarations with reset values
- Synchronous process with clock and reset
- The 'while True' loop pattern for continuous operation
- The 'await zdc.cycles(1)' pattern for state boundaries
"""

import zuspec.dataclasses as zdc


@zdc.dataclass
class Counter(zdc.Component):
    """A simple up/down counter with synchronous reset.
    
    Reset values are specified in the output() declaration,
    eliminating the need for explicit reset handling in the process.
    """
    
    # Input ports
    clock : zdc.bit = zdc.input()
    reset : zdc.bit = zdc.input()
    inc_en : zdc.bit = zdc.input()
    dec_en : zdc.bit = zdc.input()
    
    # Output ports with reset values
    count : zdc.u32 = zdc.output(reset=0)  # Reset value specified here
    
    @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
    async def run(self):
        """Synchronous counter process.
        
        The 'while True' loop runs continuously.
        Reset handling is automatic based on output(reset=...).
        """
        while True:
            if self.inc_en:
                self.count += 1
            elif self.dec_en:
                self.count -= 1
            await zdc.cycles(1)


if __name__ == "__main__":
    print("SPRTL Counter Example")
    print("=" * 50)
    print()
    print("This example defines a 32-bit up/down counter with:")
    print("- clock input port (1 bit)")
    print("- reset input port (1 bit)")
    print("- inc_en input port (1 bit) - increment enable")
    print("- dec_en input port (1 bit) - decrement enable")
    print("- count output port (32 bits) with reset=0")
    print()
    print("Key SPRTL features demonstrated:")
    print("- output(reset=0) specifies reset value")
    print("- 'while True' loop for continuous operation")
    print("- 'await zdc.cycles(1)' for clock cycle boundary")
    print("- No explicit reset handling in the process body")
    print()
    
    # Verify the component can be instantiated
    try:
        counter = Counter(clock=0, reset=0, inc_en=0, dec_en=0)
        print(f"Component instantiated: {counter}")
        print(f"  clock type: {type(counter.clock)}")
        print(f"  count type: {type(counter.count)}")
    except Exception as e:
        print(f"Note: Full instantiation requires runtime support: {e}")
