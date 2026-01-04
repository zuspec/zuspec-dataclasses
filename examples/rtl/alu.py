#!/usr/bin/env python3
"""
Simple ALU example demonstrating combinational logic.

This example shows:
- Multiple input/output ports
- Combinational process with @comb decorator
- Immediate assignment semantics
"""

import zuspec.dataclasses as zdc


@zdc.dataclass
class SimpleALU(zdc.Component):
    """A simple ALU with XOR and ADD operations"""
    
    # Input ports
    a : zdc.u16 = zdc.input()
    b : zdc.u16 = zdc.input()
    op : zdc.bit = zdc.input()  # 0 = XOR, 1 = ADD
    
    # Output ports
    result : zdc.u16 = zdc.output()
    
    @zdc.comb
    def _alu_logic(self):
        """Combinational ALU logic
        
        This process re-evaluates whenever inputs a, b, or op change.
        Assignments in comb processes take effect immediately.
        
        Operation:
        - When op=0: result = a XOR b
        - When op=1: result = a + b
        """
        if self.op == 0:
            self.result = self.a ^ self.b
        else:
            self.result = (self.a + self.b) & 0xFFFF  # Mask to 16 bits


@zdc.dataclass
class RegisteredALU(zdc.Component):
    """ALU with registered output - combines sync and comb"""
    
    # Input ports
    clock : zdc.bit = zdc.input()
    reset : zdc.bit = zdc.input()
    a : zdc.u16 = zdc.input()
    b : zdc.u16 = zdc.input()
    op : zdc.bit = zdc.input()
    
    # Output ports
    result : zdc.u16 = zdc.output()
    
    # Internal signal
    _alu_out : zdc.u16 = zdc.field()
    
    @zdc.comb
    def _alu_logic(self):
        """Combinational ALU calculation"""
        if self.op == 0:
            self._alu_out = self.a ^ self.b
        else:
            self._alu_out = (self.a + self.b) & 0xFFFF
    
    @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
    def _output_reg(self):
        """Register the ALU output"""
        if self.reset:
            self.result = 0
        else:
            self.result = self._alu_out


if __name__ == "__main__":
    print("ALU RTL Examples")
    print("=" * 50)
    print()
    print("SimpleALU: Pure combinational logic")
    print("- Inputs: a (16 bits), b (16 bits), op (1 bit)")
    print("- Output: result (16 bits)")
    print("- Uses @comb decorator for immediate evaluation")
    print()
    print("RegisteredALU: Combines sync and comb processes")
    print("- Comb process calculates ALU result")
    print("- Sync process registers the output")
    print("- Demonstrates how sync and comb work together")
    print()
    print("Note: This example shows the API definition.")
    print("Execution engine implementation is planned for future phases.")
