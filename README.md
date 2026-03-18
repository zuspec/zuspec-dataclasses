# Zuspec Dataclasses

A Python-embedded multi-abstraction language for modeling digital hardware from transfer-function level to register transfer level (RTL). Zuspec provides decorators and types to capture hardware model semantics with support for simulation, verification, and code generation.

## Overview

Zuspec is a Python-based DSL that:
- Supports multiple abstraction levels (behavioral to RTL)
- Provides type-safe hardware modeling with static type checking
- Enables component-based design with ports, bundles, and interfaces
- Includes built-in support for timing, synchronization, and communication
- Features profile-based validation for different target platforms

## Key Features

### 1. Type System (154 public API elements)

**Hardware Types (95 types):**
- Width-annotated integers: `u1`-`u32`, `u64`, `u128`, `i8`, `i16`, `i32`, `i64`, `i128`
- Bit types: `bit`, `bit1`-`bit8`, `bit16`, `bit32`, `bit64`
- Variable-width types: `bitv`, `bv` (width specified at field level)
- Long-form type aliases: `uint8_t`, `uint32_t`, `int32_t`, etc.

**Structural Types:**
- `Component` - Base class for structural hardware components
- `XtorComponent[T]` - Transactor components with signal-level and operation-level interfaces
- `Bundle` - Interface/port collections with directionality
- `Struct` - Data-only types with C-like alignment
- `PackedStruct` - Bitwise packed data structures

**Timing:**
- `Time` class with units: `s`, `ms`, `us`, `ns`, `ps`, `fs`
- `Timebase` protocol for time management

### 2. Decorators (17 decorators)

**Class Decorators:**
- `@dataclass(profile=...)` - Define hardware components with optional profile validation

**Field Decorators:**
- `field()` - General field declaration with metadata support
- `const()` - Compile-time/construction-time parameters
- `input()` / `output()` - Signal directionality for RTL
- `bundle()` / `mirror()` / `monitor()` - Interface instantiation with optional kwargs
- `port()` / `export()` - Method-based communication channels
- `inst()` - Automatic instance construction
- `tuple()` - Fixed-size tuples

**Method Decorators:**
- `@process` - Always-running async processes
- `@sync(clock=..., reset=...)` - Synchronous (clocked) processes with deferred assignment
- `@comb` - Combinational (immediate) processes
- `@invariant` - Structural invariants for validation
- `bind()` - Connection specifications

### 3. Parameterization

**Const Parameters:**
```python
@zdc.dataclass
class WishboneInitiator(zdc.Bundle):
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
```

**Width Expressions:**
```python
dat_w : zdc.bitv = zdc.output(width=lambda s: s.DATA_WIDTH)
sel : zdc.bitv = zdc.input(width=lambda s: int(s.DATA_WIDTH/8))
```

**Bundle Instantiation with Kwargs:**
```python
init : WishboneInitiator = zdc.bundle(
    kwargs=lambda s: dict(
        DATA_WIDTH=s.DATA_WIDTH,
        ADDR_WIDTH=s.ADDR_WIDTH))
```

### 4. Communication Primitives

**TLM Interfaces (6 protocols):**
- `GetIF[T]` / `PutIF[T]` - Basic get/put interfaces
- `ReqRspIF[Treq,Trsp]` - Request-response interface
- `Channel[T]` - Bidirectional channel
- `ReqRspChannel[Treq,Trsp]` - Initiator/target channel
- `Transport[Treq,Trsp]` - Callable transport function

**Port/Export Pattern:**
```python
class ITarget(Protocol):
    async def access(self, addr: zdc.u32, data: zdc.u32) -> zdc.u32: ...

@zdc.dataclass
class Target(zdc.Component):
    api : ITarget = zdc.export()
    
    def __bind__(self):
        return {self.api.access: self.handle_access}
```

### 5. Synchronization

**Edge Detection (3 functions):**
- `posedge(signal)` - Wait for positive edge
- `negedge(signal)` - Wait for negative edge  
- `edge(signal)` - Wait for any edge

**Timing:**
```python
await self.wait(zdc.Time.ns(10))  # Wait 10 nanoseconds
await posedge(self.clock)          # Wait for clock edge
```

**Resource Management:**
- `Lock` - Async mutex locks
- `Pool[T]` / `ClaimPool[T]` - Resource pools with arbitration
- `Memory` / `AddressSpace` - Memory modeling
- `RegFile` / `Reg` / `RegFifo` - Register modeling

### 6. Profile System

**Built-in Profiles:**
- `PythonProfile` - Permissive, standard Python types allowed
- `RetargetableProfile` - Strict, requires width-annotated types for hardware synthesis

**Usage:**
```python
from zuspec.dataclasses import dataclass, profiles

@dataclass(profile=profiles.PythonProfile)
class SoftwareModel:
    x: int  # OK with PythonProfile

@dataclass(profile=profiles.RetargetableProfile)
class HardwareModel:
    x: uint32_t  # Width-annotated type required
```

**Custom Profiles:**
Extend `Profile` and `ProfileChecker` to create custom validation rules.

### 7. Static Type Checking

**MyPy Plugin Integration:**
- Validates field types based on profile
- Checks width annotations for hardware types
- Enforces correct decorator usage
- Validates method bindings

Configure in `pyproject.toml`:
```toml
[tool.mypy]
plugins = ["zuspec.dataclasses.mypy.plugin"]
```

## Quick Start

### Installation

```shell
# Using IVPM (recommended for developers)
uvx ivpm update

# Or install directly
pip install zuspec-dataclasses
```

### Simple Counter Example

```python
import zuspec.dataclasses as zdc

@zdc.dataclass
class Counter(zdc.Component):
    clock : zdc.bit = zdc.input()
    reset : zdc.bit = zdc.input()
    count : zdc.u32 = zdc.output()
    
    @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
    def _count_proc(self):
        if self.reset:
            self.count = 0
        else:
            self.count = self.count + 1
```

### Component Communication Example

```python
@zdc.dataclass
class Producer(zdc.Component):
    data : zdc.GetIF[zdc.u32] = zdc.port()
    
    @zdc.process
    async def run(self):
        for i in range(10):
            value = await self.data.get()
            print(f"Received: {value}")
```

### 8. PSS Activities

PSS compound actions express complex test intent using an **activity** — a
sequential or parallel composition of sub-action traversals.

#### Flow-Object and Resource Base Types

```python
import zuspec.dataclasses as zdc

@zdc.dataclass
class DataBuff(zdc.Buffer):          # PSS buffer flow-object
    seg: zdc.u32 = zdc.rand()

@zdc.dataclass
class DmaChannel(zdc.Resource):      # PSS resource
    priority: zdc.u4 = zdc.rand()
```

| Base type   | PSS concept         | Field helpers       |
|-------------|---------------------|---------------------|
| `Buffer`    | Buffer flow-object  | `input()`, `output()` |
| `Stream`    | Stream flow-object  | `input()`, `output()` |
| `State`     | State flow-object   | `input()`, `output()` |
| `Resource`  | Resource            | `lock()`, `share()` |

#### Compound Action with Activity

```python
@zdc.dataclass
class WriteData(zdc.Action[DmaComponent]):
    data: DataBuff   = zdc.output()
    chan: DmaChannel  = zdc.lock()
    size: zdc.u8     = zdc.rand()

    async def body(self): ...            # atomic action

@zdc.dataclass
class ReadData(zdc.Action[DmaComponent]):
    data: DataBuff   = zdc.input()
    chan: DmaChannel  = zdc.lock()

    async def body(self): ...

@zdc.dataclass
class DmaXfer(zdc.Action[DmaComponent]):
    wr: WriteData = zdc.field(default=None)
    rd: ReadData  = zdc.field(default=None)

    async def activity(self):
        self.wr()                        # traverse wr sequentially
        with self.rd():                  # traverse rd with inline constraint
            self.rd.chan.priority > 5
```

The `@zdc.dataclass` decorator detects `async def activity(self)`, parses it
from the Python AST (never executing it), and stores the structured IR on
`DmaXfer.__activity__`.

#### Scheduling Blocks

```python
async def activity(self):
    with zdc.parallel():               # concurrent traversals
        self.a()
        self.b()

    with zdc.parallel(join_first=1):   # stop after first branch finishes
        self.x()
        self.y()

    with zdc.schedule():               # PSS schedule block
        self.p()
        self.q()

    with zdc.atomic():                 # atomic (exclusive) region
        self.z()
```

#### Control Flow

```python
async def activity(self):
    # Repeat (count loop)
    for i in range(self.count):
        self.write()

    # Foreach (collection iteration)
    for item in self.data_array:
        self.process()

    # Select (non-deterministic choice)
    with zdc.select():
        with zdc.branch(weight=70):
            self.fast_write()
        with zdc.branch(weight=30):
            self.slow_write()

    # Conditional
    if self.size > 64:
        self.big_xfer()
    else:
        self.small_xfer()

    # Bind flow objects
    bind(self.producer.data_out, self.consumer.data_in)
```

#### Anonymous Traversal (`do`)

```python
async def activity(self):
    zdc.do(WriteData)                  # anonymous traversal
    with zdc.do(ReadData) as rd:       # anonymous with label + constraints
        rd.size < 256
```

#### Type Extensions (`@zdc.extend`)

```python
@zdc.extend
class WriteDataExt(WriteData):
    tag: zdc.u4 = zdc.rand()          # adds a field to WriteData
```

`@zdc.extend` sets `__is_extension__ = True` and `__extends__` on the class.
Multiple extensions of the same base imply a PSS `schedule` composition.

#### Accessing the Activity IR

```python
from zuspec.dataclasses.ir.activity import ActivitySequenceBlock, ActivityTraversal

ir = DmaXfer.__activity__             # ActivitySequenceBlock
for stmt in ir.stmts:
    if isinstance(stmt, ActivityTraversal):
        print(stmt.handle, stmt.inline_constraints)
```

## Documentation

- **[User Guide](docs/intro.rst)** - Comprehensive language introduction
- **[Types Reference](docs/types.rst)** - Complete type system documentation
- **[Runtime Guide](docs/runtime.rst)** - Runtime and simulation details
- **[Profile Checker Guide](docs/profile_checker_guide.md)** - Profile system and validation
- **[Parameterization Guide](PARAMETERIZATION_SUMMARY.md)** - Parameter and configuration support
- **[Examples](examples/)** - SPI model, RTL counter, ALU, and more

## Project Status

**Implemented Features:**
- ✅ Core type system with 95+ hardware types
- ✅ 17 decorators for component definition
- ✅ Parameterization with const fields and lambda expressions
- ✅ Profile system with MyPy integration
- ✅ TLM communication primitives
- ✅ Port/Export binding mechanism
- ✅ Synchronization primitives (posedge, negedge, edge)
- ✅ Resource management (Lock, Pool, Memory)
- ✅ Pure Python runtime with async support
- ✅ Static type checking via MyPy plugin
- ✅ PSS Activities — compound actions, scheduling blocks, control flow, flow-objects, resources
- ✅ `@zdc.extend` for PSS type extensions

**In Progress:**
- 🔄 RTL execution engine for sync/comb processes
- 🔄 Code generation backends (SystemVerilog, C++)
- 🔄 Randomization and constraint solving
- 🔄 Coverage collection

## Architecture

Zuspec consists of four independent layers:

1. **Language Facade** (`src/zuspec/dataclasses/`) - Decorators, types, and base classes
2. **Pure-Python Runtime** (`src/zuspec/dataclasses/rt/`) - Async execution engine
3. **IR Data Model** (`src/zuspec/dataclasses/ir/`) - AST-like representation
4. **Processing Tools** - Analysis and code generation (separate packages)

## Development

### Setup

```shell
# Fetch dependencies
uvx ivpm update

# Run tests
pytest tests/

# Run type checking
mypy src/ --config-file pyproject.toml
pyright src/
```

### Project Structure

```
src/zuspec/dataclasses/
├── __init__.py          # Main API exports with __all__
├── decorators.py        # @dataclass, @sync, @comb, field(), lock(), share(), extend(), etc.
├── types.py             # Type system (Component, Bundle, Buffer, Stream, State, Resource, u32, etc.)
├── activity_parser.py   # ActivityParser — AST parser for activity() methods
├── activity_dsl.py      # DSL stubs: do, parallel, schedule, select, branch, bind, …
├── tlm.py              # TLM interfaces (GetIF, PutIF, Channel)
├── profiles.py         # Profile system and validators
├── data_model_factory.py # IR construction
├── rt/                 # Pure Python runtime
│   ├── obj_factory.py  # Object construction
│   ├── comp_impl_rt.py # Component implementation
│   ├── edge.py         # Edge detection
│   └── ...
├── ir/                 # IR data model
│   ├── activity.py     # Activity IR nodes (ActivitySequenceBlock, ActivityParallel, …)
│   └── ...
└── mypy/              # MyPy plugin for static checking
```

## Contributing

Contributions welcome! Key areas:
- RTL execution engine development
- Backend code generators
- Additional profiles for specific platforms
- Documentation improvements
- Example models

## License

Apache License 2.0 - See LICENSE file

## References

- [IVPM Package Manager](https://fvutils.github.io/ivpm/)
- [Sphinx Documentation](docs/)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- [RTL Implementation Guide](docs/RTL_IMPLEMENTATION_COMPLETE.md)
