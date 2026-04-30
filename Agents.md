# Zuspec Language

The `zuspec-dataclasses` project provides the `zuspec.dataclasses`
Python package, which defines types and decorators for capturing
models of digital hardware.

See [SKILL.md](SKILL.md) for the full agent skill (overview + construct
reference). Deeper documentation lives in the `.rst` and `.md` files
under `docs/`.

Note that processing tools for Zuspec classes require access to the
source location. Agent tools cannot generate strings to use instead.
Temp files must be used instead to ensure Zuspec classes have a source location.

---

## Overview

Zuspec is a Python-embedded modeling language. It uses ordinary Python
syntax and class definitions, but attaches special semantics to types that
inherit from Zuspec base classes and are decorated with `@zdc.dataclass`.

A Zuspec model is composed of four layers:

| Layer | Purpose |
|---|---|
| **Language façade** | Base classes and decorators (`zdc.*`) that identify modeling elements |
| **Pure-Python runtime** | Executes the model as a Python simulation without any code generation |
| **Data model** | AST-like IR built from source classes; used by analysis and synthesis tools |
| **Processing tools** | Operate on the data model to emit C, SV, synthesis artifacts, etc. |

These layers are kept independent: the language façade must not depend on
the runtime, and the runtime must not depend on the data model.

Zuspec supports multiple abstraction levels in a single unified language:

- **Algorithmic / behavioral** – functional correctness, approximate timing
- **Cycle-accurate / MLS** – clock-boundary transitions, pipeline modeling
- **RTL** – synthesizable `@zdc.sync` / `@zdc.comb` descriptions

---

## Core Constructs

These classes and decorators are used at every abstraction level.

### `zdc.Component`

The primary structural building block. Components form hierarchical trees;
child component instances are created automatically for fields of
`Component` type.

```python
@zdc.dataclass
class MyBlock(zdc.Component):
    clk: zdc.bit = zdc.input()
    rst: zdc.bit = zdc.input()
```

Key patterns:
- Declare top-level ports with `zdc.input()` / `zdc.output()`
- Declare child components with `zdc.field()` (or `zdc.inst()`)
- Override `__bind__()` to wire ports between children

### `@zdc.dataclass`

Required decorator on every Zuspec class. Applies dataclass-style field
processing and registers the class with the Zuspec data model.

### Fields and Ports

| Decorator | Role |
|---|---|
| `zdc.input()` | Drives a value into the component |
| `zdc.output()` | Exposes a value from the component |
| `zdc.field()` | Sub-component instance or data field |
| `zdc.port()` | Initiator side of an interface connection |
| `zdc.export()` | Target side of an interface connection |
| `zdc.reg()` | Register-backed field |
| `zdc.array()` | Array field |

### Binding (`__bind__`)

Port connections are expressed as a `dict` mapping in `__bind__()` or
inline via the `bind=` argument to `zdc.field()`.

```python
def __bind__(self): return {
    self.child.clk: self.clk,
    self.child.rst: self.rst,
}
```

### Scalar Types

`zdc` exposes a family of fixed-width integer types: `zdc.u8`, `zdc.u16`,
`zdc.u32`, `zdc.u64`, `zdc.i8` … `zdc.i64`, `zdc.bit`, and parameterized
`zdc.bv[N]` / `zdc.bitv[N]`.

### `zdc.Struct` / `zdc.PackedStruct`

Plain data aggregates used for passing structured values between components
or across interfaces.

### `zdc.enum`

Decorator for defining Zuspec-aware enumeration types used in constraints
and fields.

---

## Design Constructs

### RTL Constructs

RTL constructs produce synthesizable descriptions. The synthesizer maps
them to standard flip-flop and combinational logic primitives.

#### `@zdc.sync`

Clocked process; all output assignments are non-blocking (registered on
the active clock edge). Reset behavior is modeled with an `if self.rst:`
guard.

```python
@zdc.sync(clock=lambda s: s.clk, reset=lambda s: s.rst)
def tick(self):
    if self.rst:
        self.count = 0
    else:
        self.count += 1
```

#### `@zdc.comb`

Combinational process; re-evaluated whenever any referenced input changes.

```python
@zdc.comb
def alu(self):
    self.result = self.a + self.b
```

Synthesis attributes (e.g., `parallel_case`, `full_case`) can be attached
via pragma comments on `if`/`elif` chains.

#### `zdc.RegFile` / `zdc.Reg`

Register files map directly to hardware registers. `zdc.RegFile` groups
related `zdc.Reg` fields and can be exposed in an `AddressSpace`.

```python
@zdc.dataclass
class CtrlRegs(zdc.RegFile):
    ctrl:   zdc.Reg[zdc.u8]  = zdc.field()
    status: zdc.Reg[zdc.u8]  = zdc.field()
```

#### `zdc.Memory` / `zdc.AddressSpace`

`zdc.Memory` models a block of addressable memory. `zdc.AddressSpace`
composes multiple memories and register files at specified offsets.

#### Clock and Reset Domains (`zdc.ClockDomain`, `zdc.ResetDomain`)

Explicit domain declarations used for CDC analysis and multi-clock designs.
`zdc.TwoFFSync` and `zdc.AsyncFIFO` are built-in CDC crossing primitives.

### Medium-Level Synthesis (MLS) Constructs

MLS sits between behavioral and RTL. It models cycle boundaries explicitly
without requiring full RTL signal declarations.

#### `@zdc.pipeline` (async pipeline)

Describes a multi-stage pipeline as an `async def` with `async with
zdc.pipeline.stage()` blocks marking stage boundaries.

```python
@zdc.pipeline(clock=lambda s: s.clk)
async def execute(self):
    async with zdc.pipeline.stage() as IF:
        inst = self.imem[self.pc]
    async with zdc.pipeline.stage() as EX:
        result = inst.rs1 + inst.rs2
    async with zdc.pipeline.stage() as WB:
        self.rf[inst.rd] = result
```

#### Pipeline Hazard Resources

`zdc.pipeline.resource()` declares a set of resources (e.g., a register
file) that stages must coordinate access to. Hazard policies:

| Lock type | Behavior |
|---|---|
| `zdc.QueueLock` | Stall on conflict, no bypass |
| `zdc.BypassLock` | Stall + forwarding network |
| `zdc.RenameLock` | Tomasulo-style out-of-order rename |

#### `zdc.cycles(n)`

Used inside `@zdc.sync` methods to introduce explicit state boundaries that
map to FSM transitions at synthesis time.

#### `@zdc.stage` (legacy sync pipeline)

Older synchronous pipeline decorator. Prefer the `async` `@zdc.pipeline`
API for new designs.

---

## Test and Verification Constructs

### Randomization

`zdc.randomize(obj)` / `zdc.randomize_with(obj, lambda ...)` solve
constraints declared on a class and populate `rand`-annotated fields.

Fields annotated with `zdc.rand` participate in randomization; `zdc.randc`
gives cyclic randomization (SystemVerilog `randc` semantics).

### Constraints

Constraints are expressed as methods decorated with `@zdc.constraint`:

```python
@zdc.dataclass
class Packet(zdc.Struct):
    length: zdc.u16 = zdc.rand()

    @zdc.constraint
    def c_length(self):
        self.length >= 64
        self.length <= 1500
```

Helper functions: `zdc.implies`, `zdc.dist`, `zdc.unique`, `zdc.sum`,
`zdc.ascending`, `zdc.solve_order`.

### Coverage

```python
@zdc.dataclass
class PktCov(zdc.Covergroup):
    @zdc.coverpoint
    def cp_length(self): return self.pkt.length

    @zdc.cross
    def cx_len_proto(self): return [self.cp_length, self.cp_proto]
```

`zdc.binsof`, `zdc.cross_bins`, `zdc.cross_ignore`, `zdc.cross_illegal`
provide bin filtering for cross coverage.

### Actions and Activities

`zdc.Action` classes model atomic test steps that can be composed into
activity graphs using the activity DSL:

| DSL call | Meaning |
|---|---|
| `zdc.do(ActionClass)` | Execute one action |
| `zdc.sequence(...)` | Run actions in order |
| `zdc.parallel(...)` | Run actions concurrently |
| `zdc.select(...)` | Non-deterministic choice |
| `zdc.replicate(n, ...)` | Repeat N times |

### Contract Decorators

`@zdc.requires` / `@zdc.ensures` express pre- and post-conditions on
component methods. Violations raise `zdc.ContractViolation`.

### `zdc.ScenarioRunner` / `zdc.run_action`

Top-level entry points for executing action-based test scenarios. Use
`run_action_sync` for a non-async caller context.

---

## Behavioral Modeling Constructs

### `zdc.IfProtocol`

Base class for interface protocol definitions. Subclass it and declare
`async` methods to define a typed, synthesizer-aware interface.

```python
class BusIF(zdc.IfProtocol, max_outstanding=4):
    async def read(self, addr: zdc.u32) -> zdc.u32: ...
    async def write(self, addr: zdc.u32, data: zdc.u32) -> None: ...
```

Use as a `zdc.port()` / `zdc.export()` type on a component.

### `zdc.Queue` / `zdc.queue`

Typed FIFO queues for passing data between concurrent behaviors. Used with
`async get` / `async put` patterns.

### `zdc.spawn` / `zdc.SpawnHandle`

Spawn concurrent coroutines within a component's simulation context.
`SpawnHandle` allows the caller to join or cancel the spawned task.

### `zdc.Event`

Supports interrupt-style signaling. Backed by `asyncio.Event`. Components
can `await` an event or `bind` a callback to it via the `at` field.

### `zdc.simulate`

Convenience entry point that constructs a root component and runs the
simulation to completion (or until `shutdown()` is called).

### `zdc.SimDomain`

Manages a shared simulation time context across a component tree.
Required when composing multiple independently-timed subsystems.

### `zdc.posedge` / `zdc.negedge` / `zdc.edge`

Awaitable edge detectors used in behavioral processes to synchronize on
clock or signal transitions.

### `zdc.gather`

Collects results from multiple concurrent awaitables, similar to
`asyncio.gather` but integrated with Zuspec's simulation time.

### `zdc.Buffer`, `zdc.Stream`, `zdc.State`, `zdc.Resource`

Flow-object base classes for PSS-style resource and data-flow modeling:

| Class | Semantics |
|---|---|
| `zdc.Buffer` | Consumed once (point-to-point data) |
| `zdc.Stream` | Streamed data (FIFO semantics) |
| `zdc.State` | Shared mutable state |
| `zdc.Resource` | Locked/released hardware resource |

### TLM Channels

`zdc.Channel`, `zdc.PutIF`, `zdc.GetIF`, `zdc.ReqRspChannel`,
`zdc.ReqRspIF`, `zdc.Transport` provide Transaction-Level Modeling
primitives for abstract bus and interface modeling.

