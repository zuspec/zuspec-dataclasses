# Zuspec Dataclasses API Reference

Quick reference for all public API elements (154 total).

## Table of Contents
- [Decorators](#decorators)
- [Types](#types)
- [Base Classes](#base-classes)
- [TLM Interfaces](#tlm-interfaces)
- [Synchronization](#synchronization)
- [Resource Management](#resource-management)
- [Profiles](#profiles)

## Decorators

### Class Decorators

#### `@dataclass(cls=None, *, profile=None, **kwargs)`
Marks a class as a Zuspec dataclass with optional profile validation.

```python
@zdc.dataclass
class MyComponent(zdc.Component):
    ...

@zdc.dataclass(profile=profiles.RetargetableProfile)
class HardwareModel(zdc.Component):
    ...
```

### Field Decorators

#### `field(rand=False, init=None, default_factory=None, default=None, metadata=None, size=None, bounds=None, width=None)`
General field declaration with rich metadata support.

```python
_internal : zdc.u32 = zdc.field(default=0)
_data : zdc.u8 = zdc.field(bounds=(0, 255))
```

#### `const(default=None)`
Compile-time/construction-time parameter (structural type parameter).

```python
DATA_WIDTH : zdc.u32 = zdc.const(default=32)
ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
```

#### `input(width=None)`
Marks an input signal with optional width expression.

```python
clock : zdc.bit = zdc.input()
data : zdc.bitv = zdc.input(width=lambda s: s.DATA_WIDTH)
```

#### `output(width=None)`
Marks an output signal with optional width expression.

```python
result : zdc.u32 = zdc.output()
status : zdc.bitv = zdc.output(width=lambda s: s.WIDTH)
```

#### `bundle(default_factory=MISSING, kwargs=None)`
Instantiates a bundle with declared directionality.

```python
bus : MyBus = zdc.bundle(
    kwargs=lambda s: dict(WIDTH=s.DATA_WIDTH))
```

#### `mirror(default_factory=MISSING, kwargs=None)`
Instantiates a bundle with flipped directionality.

```python
mirrored : MyBus = zdc.mirror()
```

#### `monitor(default_factory=MISSING, kwargs=None)`
Instantiates a bundle for passive monitoring.

```python
mon : MyBus = zdc.monitor()
```

#### `port()`
Declares an API consumer (must be bound to an export).

```python
api : IMyInterface = zdc.port()
```

#### `export()`
Declares an API provider (implementation specified in `__bind__`).

```python
service : IMyInterface = zdc.export()
```

#### `inst(default_factory=MISSING, kwargs=None, elem_factory=None, size=None)`
Automatically constructed instance based on annotated type.

```python
counter : Counter = zdc.inst(kwargs=lambda s: dict(WIDTH=s.WIDTH))
subcomps : List[SubComp] = zdc.inst(elem_factory=SubComp, size=4)
```

#### `tuple(size=0, elem_factory=None)`
Fixed-size tuple with automatic element construction.

```python
regs : Tuple[Reg, ...] = zdc.tuple(size=8, elem_factory=Reg)
```

### Method Decorators

#### `@process`
Marks an async method as an always-running process (started automatically).

```python
@zdc.process
async def run(self):
    for i in range(10):
        await self.wait(zdc.Time.ns(10))
```

#### `@sync(clock=None, reset=None)`
Synchronous (clocked) process with deferred assignment semantics.

```python
@zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
def _counter(self):
    if self.reset:
        self.count = 0
    else:
        self.count = self.count + 1
```

#### `@comb`
Combinational process with immediate assignment semantics.

```python
@zdc.comb
def _logic(self):
    self.out = self.a ^ self.b
```

#### `@invariant`
Structural invariant that must always hold.

```python
@zdc.invariant
def bounds_check(self) -> bool:
    return 0 <= self.value <= 100
```

#### `bind()`
Helper for type-safe binding specifications (used in `__bind__`).

```python
def __bind__(self):
    return {
        self.api.method: self.impl_method
    }
```

## Types

### Integer Types (Width-Annotated)

**Unsigned (short form):**
`u1`, `u2`, `u3`, `u4`, `u5`, `u6`, `u7`, `u8`, `u9`, `u10`, `u11`, `u12`, `u13`, `u14`, `u15`, `u16`, `u17`, `u18`, `u19`, `u20`, `u21`, `u22`, `u23`, `u24`, `u25`, `u26`, `u27`, `u28`, `u29`, `u30`, `u31`, `u32`, `u64`, `u128`

**Unsigned (long form):**
`uint1_t` through `uint32_t`, `uint64_t`, `uint128_t`

**Signed:**
`i8`, `i16`, `i32`, `i64`, `i128` (short form)
`int8_t`, `int16_t`, `int32_t`, `int64_t`, `int128_t` (long form)

### Bit Types

`bit` (alias for `u1`), `bit1`, `bit2`, `bit3`, `bit4`, `bit5`, `bit6`, `bit7`, `bit8`, `bit16`, `bit32`, `bit64`

### Variable-Width Types

- `bitv` / `bv` - Variable-width bit vector (width specified via `width=` parameter)

```python
data : zdc.bitv = zdc.output(width=lambda s: s.DATA_WIDTH)
```

### Width Annotation Helpers

- `SignWidth` - Base class for width annotations
- `U(width)` - Unsigned width annotation
- `S(width)` - Signed width annotation

## Base Classes

### `TypeBase`
Marker base for all Zuspec types.

### `Component`
Base class for structural hardware components.

```python
@zdc.dataclass
class MyComponent(zdc.Component):
    def __bind__(self):
        return {...}  # Connection specifications
    
    async def wait(self, amt: Time = None):
        """Wait for specified time or delta cycle"""
    
    def time(self) -> Time:
        """Get current simulation time"""
```

### `XtorComponent[T]`
Transactor with both signal-level and operation-level interfaces.

```python
@zdc.dataclass
class MyTransactor(zdc.XtorComponent[IMyAPI]):
    xtor_if : IMyAPI = zdc.export()  # Automatic export
    
    # Signal-level interface
    bus : MyBus = zdc.bundle()
    
    def __bind__(self):
        return {
            self.xtor_if.method: self.impl
        }
```

### `Bundle`
Base class for interface/port collections with directionality.

```python
@zdc.dataclass
class MyBus(zdc.Bundle):
    WIDTH : zdc.u32 = zdc.const(default=32)
    data : zdc.bitv = zdc.output(width=lambda s: s.WIDTH)
    valid : zdc.bit = zdc.output()
    ready : zdc.bit = zdc.input()
```

### `Struct`
Data-only type with C-like alignment and packing.

```python
@zdc.dataclass
class Header(zdc.Struct):
    magic : zdc.u32 = zdc.field()
    version : zdc.u16 = zdc.field()
```

### `PackedStruct`
Bitwise packed data structure (no automatic padding).

```python
@zdc.dataclass
class Instruction(zdc.PackedStruct):
    opcode : zdc.u8 = zdc.field()
    rs1 : zdc.u5 = zdc.field()
    rs2 : zdc.u5 = zdc.field()
```

## TLM Interfaces

### `GetIF[T]`
Async get interface.

```python
async def get(self) -> T: ...
def try_get(self) -> Tuple[bool, T]: ...
```

### `PutIF[T]`
Async put interface.

```python
async def put(self, value: T): ...
def try_put(self, value: T) -> bool: ...
```

### `ReqRspIF[Treq, Trsp]`
Combined request-response interface (extends PutIF and GetIF).

```python
async def put(self, req: Treq): ...
async def get(self) -> Trsp: ...
```

### `Channel[T]`
Bidirectional channel protocol.

```python
@zdc.dataclass
class Channel[T](Protocol):
    put : PutIF[T]
    get : GetIF[T]
```

### `ReqRspChannel[Treq, Trsp]`
Request-response channel with initiator and target interfaces.

```python
@zdc.dataclass
class ReqRspChannel[Treq, Trsp](Protocol):
    init : ReqRspIF[Treq, Trsp]
    targ : ReqRspIF[Trsp, Treq]
```

### `Transport[Treq, Trsp]`
Type alias for blocking transport function.

```python
type Transport[Treq, Trsp] = Callable[[Treq], Trsp]
```

## Synchronization

### Edge Detection

#### `async posedge(signal)`
Wait for positive edge of a signal.

```python
await zdc.posedge(self.clock)
```

#### `async negedge(signal)`
Wait for negative edge of a signal.

```python
await zdc.negedge(self.reset_n)
```

#### `async edge(signal)`
Wait for any edge (positive or negative).

```python
await zdc.edge(self.strobe)
```

### Timing

#### `Time`
Time value with unit specification.

**Constructors:**
- `Time.s(amt)` - Seconds
- `Time.ms(amt)` - Milliseconds
- `Time.us(amt)` - Microseconds
- `Time.ns(amt)` - Nanoseconds
- `Time.ps(amt)` - Picoseconds
- `Time.fs(amt)` - Femtoseconds
- `Time.delta()` - Delta cycle (zero time)

**Conversions:**
- `as_s()`, `as_ms()`, `as_us()`, `as_ns()`, `as_ps()`, `as_fs()`

**Operations:**
```python
t = zdc.Time.ns(10)
t2 = t * 2  # 20ns
t3 = t + zdc.Time.ns(5)  # 15ns
```

#### `TimeUnit`
Enum: `S`, `MS`, `US`, `NS`, `PS`, `FS`

#### `Timebase`
Protocol for time management (implemented by runtime).

## Resource Management

### `Lock`
Async mutex lock for coordinating access.

```python
lock = zdc.Lock()  # Created by runtime

async with lock:
    # Critical section
    shared_resource.modify()
```

### `Pool[T]`
Base protocol for resource pools.

### `ListPool[T]`
Pool backed by a list.

```python
@zdc.dataclass
class ListPool[T](zdc.Pool[T]):
    elems : List[T]
    
    def __getitem__(self, idx: int) -> T: ...
    def get(self, idx: int) -> T: ...
    @property
    def size(self) -> int: ...
```

### `ClaimPool[T, Tc]`
Pool with claim-based arbitration.

```python
async def lock(self, i: int) -> T:
    """Acquire for read-write access"""

async def share(self, i: int) -> T:
    """Acquire for read-only access"""

def drop(self, i: int):
    """Release resource"""
```

### Memory Modeling

#### `Memory`
Memory region with address space.

#### `AddressSpace`
Top-level address space container.

#### `AddrHandle`
Handle to an address in memory.

### Register Modeling

#### `RegFile`
Register file with conditional wait support.

```python
async def when(self, regs: List[Reg], cond: Callable[[List], bool]):
    """Wait for condition on multiple registers"""
```

#### `Reg`
Single register.

#### `RegFifo`
FIFO-based register.

## Profiles

### Built-in Profiles

#### `PythonProfile`
Permissive profile - allows standard Python types.

```python
@zdc.dataclass(profile=zdc.profiles.PythonProfile)
class SoftwareModel:
    count: int  # Standard Python int OK
    name: str   # Standard Python str OK
```

#### `RetargetableProfile`
Strict profile - requires width-annotated types for hardware synthesis.

```python
@zdc.dataclass(profile=zdc.profiles.RetargetableProfile)
class HardwareModel:
    count: zdc.u32   # Must use width-annotated type
    flags: zdc.u8    # int would be rejected
```

### Profile Base Classes

#### `Profile`
Base class for defining profiles.

```python
class MyProfile(Profile):
    name = "my_profile"
    
    def get_checker(self):
        return MyProfileChecker()
```

#### `ProfileChecker`
Protocol defining validation interface.

```python
class ProfileChecker(Protocol):
    def check_field_type(self, field_name: str, field_type: Type) -> Optional[str]:
        """Return error message if type invalid, None if OK"""
```

### Profile Registry

#### `get_profile_by_name(name: str) -> Optional[Profile]`
Look up profile by name from registry.

```python
profile = zdc.profiles.get_profile_by_name("retargetable")
```

## Constants and Utilities

### `DataModelFactory`
Factory for creating IR data model from Python classes.

### Submodules

- `ir` - Intermediate representation (AST-like data model)
- `profiles` - Profile system and validators
- `rt` - Pure Python runtime implementation

## Type Checking

To enable MyPy plugin for profile validation:

```toml
# pyproject.toml
[tool.mypy]
plugins = ["zuspec.dataclasses.mypy.plugin"]
```

To use pyright (automatically works with `__all__` exports):

```shell
pyright src/
```

## See Also

- [README.md](README.md) - Project overview and quick start
- [docs/intro.rst](docs/intro.rst) - Comprehensive language introduction
- [docs/types.rst](docs/types.rst) - Type system details
- [docs/runtime.rst](docs/runtime.rst) - Runtime and execution
- [PARAMETERIZATION_SUMMARY.md](PARAMETERIZATION_SUMMARY.md) - Parameterization guide
