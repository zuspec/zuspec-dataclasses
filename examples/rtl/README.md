# RTL Modeling Examples

This directory contains examples demonstrating the RTL modeling features of zuspec-dataclasses.

## Examples

### counter.py
A simple 32-bit up-counter demonstrating:
- Input/output port declarations using `bit` types
- `@sync` decorator for synchronous processes
- Clock and reset signal handling
- Deferred assignment semantics in sync processes

```python
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
```

### alu.py
Simple ALU examples demonstrating:
- Combinational logic with `@comb` decorator
- Multiple input/output ports
- Combining sync and comb processes
- Immediate assignment semantics in comb processes

```python
@zdc.dataclass
class SimpleALU(zdc.Component):
    a : zdc.bit16 = zdc.input()
    b : zdc.bit16 = zdc.input()
    result : zdc.bit16 = zdc.output()
    
    @zdc.comb
    def _alu_logic(self):
        self.result = self.a ^ self.b
```

## Key Concepts

### Port Declarations
- Use `zdc.input()` for input ports
- Use `zdc.output()` for output ports
- Port types can be any scalar type (bit, bit8, bit16, bit32, bit64, etc.)

### Synchronous Processes (@sync)
- Execute on positive edge of clock or reset
- Assignments are **deferred** - take effect after method completes
- Must specify clock and reset signals via lambda expressions
- Reading a signal returns its value from before the current evaluation

### Combinational Processes (@comb)
- Re-evaluate automatically when any read signal changes
- Assignments are **immediate** - take effect right away
- No clock or reset needed
- Used for pure combinational logic

### Bit Types
- `bit` or `bit1`: 1-bit signal
- `bit2` through `bit64`: N-bit signals
- For wider signals, use `Annotated[int, U(width)]` directly

## Running Examples

```bash
# View the counter example
python examples/rtl/counter.py

# View the ALU examples
python examples/rtl/alu.py
```

## Implementation Status

These examples demonstrate the **API definition layer** (Phase 1-4 of the implementation plan).

Currently implemented:
- ✅ Bit type aliases (bit, bit1-bit64)
- ✅ Port declarations (input/output)
- ✅ @sync and @comb decorators
- ✅ Datamodel extensions for RTL

Planned for future phases:
- ⏳ Datamodel factory processing (Phase 3.2, 4.2)
- ⏳ Runtime execution engine (Phase 3.3, 4.4)
- ⏳ Port binding validation (Phase 5)
- ⏳ Event-driven simulation
- ⏳ Waveform generation (VCD)
- ⏳ SystemVerilog code generation

See `docs/notes/rtl.md` for the complete implementation plan.
