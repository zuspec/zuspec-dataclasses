# RTL Modeling Quick Start Guide

## Basic Concepts

### Component Definition
```python
import zuspec.dataclasses as zdc

@zdc.dataclass
class MyComponent(zdc.Component):
    # Ports
    clock : zdc.bit = zdc.input()
    reset : zdc.bit = zdc.input()
    data_in : zdc.bit8 = zdc.input()
    data_out : zdc.bit8 = zdc.output()
    
    # Internal signals
    counter : zdc.bit8 = zdc.field()
```

### Synchronous Process (@sync)
```python
@zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
def _my_proc(self):
    if self.reset:
        self.counter = 0
    else:
        self.counter = self.counter + 1
```

### Combinational Process (@comb)
```python
@zdc.comb
def _my_logic(self):
    self.data_out = self.data_in + self.counter
```

## Simulation

### Basic Simulation
```python
from zuspec.dataclasses.rt.rtl_simulator import RTLSimulator

# Create simulator
sim = RTLSimulator(MyComponent)

# Apply reset
sim.set_input("reset", 1)
sim.clock_edge("clock")

# Run simulation
sim.set_input("reset", 0)
sim.set_input("data_in", 42)
sim.clock_edge("clock")

# Read outputs
result = sim.get_output("data_out")
```

## Common Patterns

### Counter
```python
@zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
def _counter(self):
    if self.reset:
        self.count = 0
    else:
        self.count = self.count + 1
```

### Register
```python
@zdc.sync(clock=lambda s: s.clock)
def _register(self):
    self.q = self.d
```

### Multiplexer
```python
@zdc.comb
def _mux(self):
    if self.sel:
        self.out = self.in1
    else:
        self.out = self.in0
```

### State Machine
```python
@zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
def _fsm(self):
    if self.reset:
        self.state = 0
    else:
        if self.state == 0:
            if self.start:
                self.state = 1
        else:
            if self.state == 1:
                self.done = 1
                self.state = 0
```

## Data Types

| Type | Description | Example |
|------|-------------|---------|
| `zdc.bit` | 1-bit signal | `zdc.bit = zdc.input()` |
| `zdc.bit8` | 8-bit signal | `zdc.bit8 = zdc.output()` |
| `zdc.bit16` | 16-bit signal | `zdc.bit16 = zdc.field()` |
| `zdc.bit32` | 32-bit signal | `zdc.bit32 = zdc.field()` |
| `zdc.bit64` | 64-bit signal | `zdc.bit64 = zdc.field()` |

## Operators

### Arithmetic
- `+` Addition
- `-` Subtraction
- `*` Multiplication
- `//` Division
- `%` Modulo

### Bitwise
- `&` AND
- `|` OR
- `^` XOR
- `<<` Left shift
- `>>` Right shift

### Comparison
- `==` Equal
- `!=` Not equal
- `<` Less than
- `>` Greater than
- `<=` Less than or equal
- `>=` Greater than or equal

### Logical
- `and` Logical AND
- `or` Logical OR

## Simulator API

```python
# Create simulator
sim = RTLSimulator(ComponentClass)

# Set input values
sim.set_input("signal_name", value)

# Read output values
value = sim.get_output("signal_name")

# Advance clock
sim.clock_edge("clock_name")  # default: "clock"

# Evaluate all combinational logic
sim.eval_comb()
```

## Best Practices

### ✅ DO
- Use descriptive signal names
- Reset all state in sync processes
- Keep comb logic simple and focused
- Use internal signals for intermediate values
- Test with reset sequences

### ❌ DON'T
- Mix sync and comb assignments to same signal
- Create combinational loops
- Use blocking assignments in comb (always immediate)
- Forget to handle reset case
- Access signals before they're driven

## Performance Tips

| Pattern | Throughput | Use Case |
|---------|------------|----------|
| Pure comb | ~900K iter/sec | Fast computation |
| Simple sync | ~185K cycles/sec | Basic sequential logic |
| Pipeline | ~85K cycles/sec | Multi-stage designs |
| Initialization | 135 comp/sec | One-time cost |

**Optimization Tips:**
- Minimize sync processes per clock
- Reuse simulator instances
- Batch clock edges when possible
- Cache component initialization

## Debugging

### Common Issues

**Problem:** Output is always 0
```python
# ❌ Wrong - forgot to evaluate comb
sim.set_input("a", 10)
result = sim.get_output("out")  # Still 0!

# ✅ Correct - evaluate comb first
sim.set_input("a", 10)
sim.eval_comb()
result = sim.get_output("out")  # Correct value
```

**Problem:** Counter doesn't increment
```python
# ❌ Wrong - reset never released
sim.set_input("reset", 1)
sim.clock_edge("clock")  # Still in reset
sim.clock_edge("clock")  # Still in reset

# ✅ Correct - release reset
sim.set_input("reset", 1)
sim.clock_edge("clock")
sim.set_input("reset", 0)  # Release reset
sim.clock_edge("clock")    # Now counts
```

## Complete Example

```python
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.rtl_simulator import RTLSimulator

@zdc.dataclass
class Accumulator(zdc.Component):
    clock : zdc.bit = zdc.input()
    reset : zdc.bit = zdc.input()
    enable : zdc.bit = zdc.input()
    data_in : zdc.bit16 = zdc.input()
    sum_out : zdc.bit16 = zdc.output()
    
    @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
    def _accumulate(self):
        if self.reset:
            self.sum_out = 0
        else:
            if self.enable:
                self.sum_out = self.sum_out + self.data_in

# Test
sim = RTLSimulator(Accumulator)

# Reset
sim.set_input("reset", 1)
sim.clock_edge("clock")
assert sim.get_output("sum_out") == 0

# Accumulate values
sim.set_input("reset", 0)
sim.set_input("enable", 1)

sim.set_input("data_in", 10)
sim.clock_edge("clock")
assert sim.get_output("sum_out") == 10

sim.set_input("data_in", 20)
sim.clock_edge("clock")
assert sim.get_output("sum_out") == 30

# Disable accumulation
sim.set_input("enable", 0)
sim.set_input("data_in", 100)
sim.clock_edge("clock")
assert sim.get_output("sum_out") == 30  # Unchanged

print("✓ All tests passed!")
```

## See Also

- **Full Documentation:** `docs/notes/rtl_future.md`
- **Performance Results:** `tests/performance/PERFORMANCE_RESULTS.md`
- **Unit Tests:** `tests/unit/test_rtl*.py`
- **Examples:** `tests/performance/test_rtl_perf.py`
