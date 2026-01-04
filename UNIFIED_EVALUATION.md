# Unified Evaluation in Zuspec

## Overview
Zuspec uses a unified evaluation model across all types of models (hardware, software, system-level). This document explains how the evaluation infrastructure works consistently regardless of the modeling domain.

## Core Concepts

### 1. Evaluation State (`EvalState`)
The `EvalState` class manages signal values and tracks dependencies, providing:
- **Current values**: What all reads see during an evaluation cycle
- **Deferred writes**: Pending writes from sync processes
- **Watchers**: Callbacks triggered when signals change (for comb process re-evaluation)

This state management is domain-agnostic and works for any model requiring:
- Synchronized state updates (sync processes)
- Reactive re-evaluation (comb processes)

### 2. Execution (`Executor`)
The `Executor` class evaluates process bodies by:
- Reading signal values from the backend (`EvalState` or `CompImplRT`)
- Writing signal values to the backend
- Supporting both immediate and deferred write semantics

The executor is unified - the same code evaluates sync and comb processes across all modeling domains.

### 3. Simulation (`Simulator`)
The `Simulator` orchestrates evaluation:
- Executes sync processes on clock edges
- Manages comb process sensitivity and re-evaluation
- Coordinates delta-cycle scheduling

This orchestration works identically whether modeling hardware, software state machines, or system-level behavior.

## Evaluation Modes

### Sync Process Evaluation
```python
@zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
def _counter(self):
    if self.reset:
        self.count = 0
    else:
        self.count = self.count + 1
```

**Semantics**:
1. Triggered on positive edge of clock/reset
2. Reads see values from start of cycle
3. Writes are deferred until cycle completes
4. All writes commit simultaneously (atomicity)

**Use cases**: Hardware registers, synchronized state machines, coordinated updates

### Comb Process Evaluation
```python
@zdc.comb
def _logic(self):
    self.out = self.a ^ self.b
```

**Semantics**:
1. Triggered when any input changes
2. Reads see current values
3. Writes are immediate
4. Can trigger other comb processes (delta cycles)

**Use cases**: Combinational logic, reactive calculations, event-driven logic

## Unified Backend

### Component Implementation (`CompImplRT`)
The component implementation provides evaluation services through a unified interface:

```python
# Read a signal value
value = comp._impl.signal_read(comp, "my_signal")

# Write a signal value (mode-aware)
comp._impl.signal_write(comp, "my_signal", value)

# Process a clock edge
comp._impl.clock_edge(comp, "clock")

# Evaluate combinational processes
comp._impl.eval_comb(comp)
```

The implementation handles:
- Mode-aware writes (deferred for sync, immediate for comb)
- Dependency tracking for comb processes
- Delta-cycle scheduling through the timebase
- State management

### Evaluation Modes
The `EvalMode` enum tracks the current evaluation context:
- `IDLE`: Not evaluating (user code)
- `SYNC_EVAL`: Inside sync process (deferred writes)
- `COMB_EVAL`: Inside comb process (immediate writes)

This allows the same infrastructure to provide different semantics based on context.

## Model Evaluation Flow

### Clock Edge Evaluation
```
1. User sets clock signal (e.g., clock = 1)
   └─> Detects 0→1 transition
       └─> Schedules sync process evaluation at delta time

2. Delta cycle executes:
   ├─> Enter SYNC_EVAL mode
   ├─> Execute sync process body (reads old values, deferred writes)
   ├─> Exit SYNC_EVAL mode
   ├─> Commit deferred writes (atomic update)
   └─> Trigger dependent comb processes if values changed
```

### Combinational Evaluation
```
1. Signal changes (from sync commit or direct write)
   └─> Check sensitivity map
       └─> Schedule dependent comb processes

2. Delta cycle executes:
   ├─> Enter COMB_EVAL mode
   ├─> Execute comb process body (reads current, immediate writes)
   ├─> Exit COMB_EVAL mode
   └─> Trigger more comb processes if outputs changed (iterative convergence)
```

## Benefits of Unified Approach

### 1. Consistent Semantics
- Same evaluation rules across all models
- Predictable behavior regardless of domain
- Single mental model for users

### 2. Code Reuse
- Same executor for all process types
- Shared state management
- Common scheduling infrastructure

### 3. Composability
- Mix sync and comb processes freely
- Hardware and software models interact naturally
- System-level models compose from lower-level components

### 4. Extensibility
- Easy to add new evaluation modes
- Domain-specific extensions build on common foundation
- New modeling patterns don't require new infrastructure

## Examples

### Hardware Counter (Sync + Comb)
```python
@zdc.dataclass
class Counter(zdc.Component):
    clock : zdc.bit = zdc.input()
    reset : zdc.bit = zdc.input()
    count : zdc.bit32 = zdc.output()
    overflow : zdc.bit = zdc.output()
    
    @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
    def _counter(self):
        if self.reset:
            self.count = 0
        else:
            self.count = self.count + 1
    
    @zdc.comb
    def _overflow_detect(self):
        self.overflow = (self.count == 0xFFFFFFFF)
```

### Software State Machine (Sync)
```python
@zdc.dataclass
class StateMachine(zdc.Component):
    tick : zdc.bit = zdc.input()
    state : zdc.uint8_t = zdc.field()
    output : zdc.uint32_t = zdc.output()
    
    @zdc.sync(clock=lambda s: s.tick)
    def _state_update(self):
        if self.state == 0:
            self.state = 1
            self.output = 100
        elif self.state == 1:
            self.state = 0
            self.output = 200
```

### Event-Driven Logic (Comb)
```python
@zdc.dataclass
class EventProcessor(zdc.Component):
    event_a : zdc.bit = zdc.input()
    event_b : zdc.bit = zdc.input()
    priority : zdc.bit = zdc.output()
    
    @zdc.comb
    def _priority(self):
        self.priority = self.event_a & ~self.event_b
```

## Summary

Zuspec's evaluation infrastructure is **unified and domain-agnostic**:
- Works for hardware, software, and system models
- Uses consistent terminology (evaluation, not RTL-specific)
- Provides flexible semantics (sync/comb) based on modeling needs
- Enables composition and reuse across domains

The key insight is that **sync and comb processes are modeling constructs**, not RTL-specific features. They provide useful evaluation semantics for any domain requiring synchronized updates or reactive behavior.
