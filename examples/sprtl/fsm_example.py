#!/usr/bin/env python3
"""
Multi-state FSM example demonstrating await semantics in SPRTL.

This example shows:
- Multiple states created by 'await' statements
- Conditional await (await <condition>)
- Cycle delay (await zdc.cycles(N))
- Internal registers using zdc.reg()
"""

import zuspec.dataclasses as zdc


@zdc.dataclass
class SequentialProcessor(zdc.Component):
    """A sequential processor that demonstrates multi-state FSMs.
    
    The process waits for 'start', then:
    1. LOAD: Captures input data
    2. COMPUTE: Processes data (multiply by 2, add 1)
    3. STORE: Writes result
    
    Each 'await' creates a new FSM state.
    """
    
    # Input ports
    clock : zdc.bit = zdc.input()
    reset : zdc.bit = zdc.input()
    start : zdc.bit = zdc.input()
    data_in : zdc.u32 = zdc.input()
    
    # Output ports with reset values
    result : zdc.u32 = zdc.output(reset=0)
    busy : zdc.bit = zdc.output(reset=0)
    
    @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
    async def process(self):
        """Multi-state sequential process.
        
        State transitions are created at each 'await':
        - STATE 0 (IDLE): await self.start == 1
        - STATE 1 (LOAD): await zdc.cycles(1)
        - STATE 2 (COMPUTE): await zdc.cycles(1)
        - STATE 3 (STORE): await zdc.cycles(1) -> back to STATE 0
        """
        while True:
            # IDLE state: wait for start
            self.busy = 0
            await self.start == 1
            
            # LOAD state: capture input
            self.busy = 1
            temp = self.data_in
            await zdc.cycles(1)
            
            # COMPUTE state: process data
            temp = temp * 2 + 1
            await zdc.cycles(1)
            
            # STORE state: write result
            self.result = temp
            await zdc.cycles(1)


@zdc.dataclass  
class Accumulator(zdc.Component):
    """Accumulator with loop unrolling.
    
    Demonstrates:
    - Array input ports
    - Internal register with reset value
    - Loop-based computation (to be unrolled)
    """
    
    clock : zdc.bit = zdc.input()
    reset : zdc.bit = zdc.input()
    start : zdc.bit = zdc.input()
    # Note: array support would need additional implementation
    # values : zdc.array(zdc.u32, 8) = zdc.input()
    value0 : zdc.u32 = zdc.input()
    value1 : zdc.u32 = zdc.input()
    value2 : zdc.u32 = zdc.input()
    value3 : zdc.u32 = zdc.input()
    
    sum : zdc.u32 = zdc.output(reset=0)
    done : zdc.bit = zdc.output(reset=0)
    
    @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
    async def compute(self):
        while True:
            await self.start == 1
            
            # Accumulate values (would use @Unroll in full implementation)
            self.sum = 0
            self.sum = self.sum + self.value0
            self.sum = self.sum + self.value1
            self.sum = self.sum + self.value2
            self.sum = self.sum + self.value3
            
            self.done = 1
            await zdc.cycles(1)
            self.done = 0


if __name__ == "__main__":
    print("SPRTL Multi-State FSM Example")
    print("=" * 50)
    print()
    print("SequentialProcessor demonstrates:")
    print("- await <condition>: creates state that waits for condition")
    print("- await zdc.cycles(1): creates state with unconditional transition")
    print("- Multiple states in a single process")
    print()
    print("Accumulator demonstrates:")
    print("- Multiple input values")
    print("- Combinational accumulation (same state)")
    print("- Start/done handshake pattern")
