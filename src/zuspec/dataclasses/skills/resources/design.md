# Design Constructs (`zuspec.dataclasses`)

Covers RTL and Medium-Level Synthesis (MLS) constructs.  
See [core.md](core.md) for `Component`, ports, and binding basics.

---

## RTL Constructs

RTL constructs produce synthesizable descriptions mapped to flip-flops and
combinational logic.

### `@zdc.sync`

Clocked process. All output assignments are non-blocking (registered on
the active clock edge).

**Preferred (domain-based):** Inherit clock and reset from the component's
`clock_domain` / `reset_domain` by using bare `@zdc.sync`:

```python
@zdc.dataclass
class Counter(zdc.SyncComponent):
    count: zdc.bit32 = zdc.output(reset=0)

    @zdc.sync
    def tick(self):
        self.count += 1   # automatic reset handled by SyncComponent
```

**Named domain:** Fire only when a specific named `ClockDomain` ticks:

```python
@zdc.sync(domain=lambda s: s.fast_clk)
def fast_tick(self):
    self.count += 1
```

**Legacy (explicit clock/reset):** Still supported for backward compatibility.

```python
@zdc.sync(clock=lambda s: s.clk, reset=lambda s: s.rst)
def tick(self):
    if self.rst:
        self.count = 0
    else:
        self.count += 1
```

### `@zdc.comb`

Combinational process; re-evaluated whenever any referenced input changes.

```python
@zdc.comb
def alu(self):
    self.result = self.a + self.b
```

Synthesis attributes (`parallel_case`, `full_case`) can be attached via
pragma comments on `if`/`elif` chains:

```python
@zdc.comb
def decode(self):
    if self.sel == 0:  # zdc: parallel_case, full_case
        self.out = self.a
    elif self.sel == 1:
        self.out = self.b
```

See `docs/pragmas.rst` for the full pragma reference.

### `zdc.RegFile` / `zdc.Reg`

Register files map directly to hardware registers. `zdc.RegFile` groups
related `zdc.Reg` fields and can be exposed in an `AddressSpace`.

```python
@zdc.dataclass
class CtrlRegs(zdc.RegFile):
    ctrl:   zdc.Reg[zdc.u8] = zdc.field()
    status: zdc.Reg[zdc.u8] = zdc.field()
```

See `docs/regmem.md` for field-level bit-field declarations.

### `zdc.Memory` / `zdc.AddressSpace`

`zdc.Memory` models addressable memory. `zdc.AddressSpace` composes
memories and register files at specified offsets using `zdc.At`.

```python
@zdc.dataclass
class SoC(zdc.Component):
    mem:    zdc.Memory[zdc.u32] = zdc.field(size=0x10000)
    regs:   CtrlRegs            = zdc.field()
    aspace: zdc.AddressSpace    = zdc.field()

    def __bind__(self): return {
        self.aspace.mmap: (
            zdc.At(0x0000_0000, self.mem),
            zdc.At(0x1000_0000, self.regs),
        )
    }
```

`aspace.base` provides a `MemIF` handle for byte-level access to mapped
regions.

### Clock and Reset Domains

Domains eliminate explicit CLK/RST wiring from component hierarchies.
Declare a domain once at the top level; sub-components inherit it automatically.

#### `zdc.SyncComponent`

Base class for any component with `@zdc.sync` methods.  Provides default
`clock_domain` and `reset_domain` class attributes that propagate
top-down through the hierarchy.

```python
@zdc.dataclass
class Counter(zdc.SyncComponent):
    count: zdc.bit32 = zdc.output(reset=0)

    @zdc.sync          # fires on inherited clock_domain
    def tick(self):
        self.count += 1
```

#### `zdc.ClockDomain` / `zdc.ResetDomain`

Declare at class level (not as dataclass fields):

```python
@zdc.dataclass
class Top(zdc.SyncComponent):
    clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10), name="sys_clk")
    reset_domain = zdc.ResetDomain(polarity="active_low", style="sync")
    child: Counter = zdc.inst()   # inherits clock_domain / reset_domain
```

`ResetDomain` styles: `"sync"` (default), `"async"`, `"none"`.

#### `zdc.clock_domain()` — port-bound factory

Use when the top-level clock is driven by a physical port:

```python
@zdc.dataclass
class Board(zdc.SyncComponent):
    CLK: zdc.bit = zdc.input()
    clock_domain = zdc.clock_domain(
        clock=lambda s: s.CLK,
        period=zdc.Time.ns(10),
        name="sys_clk",
    )
```

#### Named (multi-clock) domains

Declare additional `ClockDomain` class attributes for multi-clock designs.
Bind `@zdc.sync` methods to a specific domain with `domain=`:

```python
@zdc.dataclass
class DualClock(zdc.SyncComponent):
    fast_clk: zdc.ClassVar[zdc.ClockDomain] = zdc.ClockDomain(
        period=zdc.Time.ns(2), name="fast_clk"
    )
    slow_count: zdc.bit32 = 0
    fast_count: zdc.bit32 = 0

    @zdc.sync                              # fires on default clock_domain
    def slow_step(self):
        self.slow_count += 1

    @zdc.sync(domain=lambda s: s.fast_clk)  # fires on fast_clk only
    def fast_step(self):
        self.fast_count += 1
```

#### `zdc.DerivedClockDomain` and `zdc.super()`

Express PLL/divider relationships for SDC generation:

```python
@zdc.dataclass
class ClockGen(zdc.SyncComponent):
    fast_clk = zdc.DerivedClockDomain(
        source=zdc.super(),   # derived from inherited clock_domain
        div=4,
        name="fast_div4",
    )
```

#### Domain binding in `__bind__`

Override a child component's domain from the parent's `__bind__`:

```python
@zdc.dataclass
class Top(zdc.SyncComponent):
    fast_clk: zdc.ClassVar[zdc.ClockDomain] = zdc.ClockDomain(
        period=zdc.Time.ns(2), name="fast_clk"
    )
    fast_worker: Worker = zdc.inst()

    def __bind__(self):
        return {
            self.fast_worker.clock_domain: self.fast_clk,
        }
```

After elaboration `fast_worker` ticks only when `fast_clk` is driven, not
when the default domain ticks.

#### SDC emission

Generate SDC/Tcl timing constraints from an elaborated design:

```python
from zuspec.dataclasses.sdc_emit import emit_sdc

async with zdc.simulate(Top) as top:
    print(emit_sdc(top))
# → create_clock -name {sys_clk} -period 10.000
# → create_generated_clock -name {fast_div4} -source {sys_clk} -divide_by 4
# → set_false_path -from {slow_clk} -to {fast_clk}   # CDC crossing
```

`emit_sdc(comp)` is a convenience wrapper; `SDCEmitPass` provides finer control.

#### CDC primitives

```python
from zuspec.dataclasses.cdc import TwoFFSync, AsyncFIFO, cdc_unchecked
```

- `zdc.TwoFFSync` — synthesizable two-FF synchronizer for single-bit crossings.  
  Automatically suppresses `set_false_path` on the launch side in SDC output.
- `zdc.AsyncFIFO` — structural placeholder for multi-bit asynchronous FIFOs.
- `@zdc.cdc_unchecked(reason)` — marks a class or field as a known-safe crossing.

---

## Medium-Level Synthesis (MLS) Constructs

MLS sits between behavioral and RTL. It models cycle boundaries explicitly
without requiring full RTL signal declarations.

### `@zdc.pipeline` (async pipeline)

Describes a multi-stage pipeline as an `async def` with
`async with zdc.pipeline.stage()` blocks marking stage boundaries.

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

See `docs/pipeline-api.rst` for the full pipeline API reference.

### Pipeline Hazard Resources

`zdc.pipeline.resource()` declares resources (e.g., a register file) that
stages must coordinate access to.

| Lock type | Behavior |
|---|---|
| `zdc.QueueLock` | Stall on conflict, no bypass |
| `zdc.BypassLock` | Stall + forwarding network |
| `zdc.RenameLock` | Tomasulo-style out-of-order rename |

### `zdc.cycles(n)`

Used inside `@zdc.sync` methods to introduce explicit state boundaries that
map to FSM transitions at synthesis time.

### `@zdc.stage` (legacy)

Older synchronous pipeline decorator. Prefer `@zdc.pipeline` for new
designs.

---

## `@zdc.proc` Synthesizable Subset

`@zdc.proc` methods describe transaction-level behaviour. The
`zuspec-synth` tool lowers them to synthesizable RTL (FSM + datapath).
Only the constructs listed here are supported in the synthesizable
subset; anything else causes synthesis to fail or produce incomplete
output.

### Supported language constructs

| Construct | Notes |
|---|---|
| `await port.method(args)` | Port call — blocking; generates FSM state + handshake |
| `await self.wait(zdc.Time.ns(n))` | Timed wait — blocking; maps to FSM state with cycle counter |
| `await zdc.tick()` | Advance exactly 1 cycle — use when the loop has no port calls |
| `await zdc.cycles(n)` | Advance N cycles |
| `if / elif / else` | Generates multiplexer or FSM branch |
| `while True:` | Outer loop; becomes the FSM loop |
| `x: int = expr` / `x = expr` | Local variable declaration and assignment |
| `self.field = expr` | Component field write (non-blocking; fires at cycle boundary) |
| `self.field` | Component field read |
| Arithmetic / bitwise / comparison operators | Direct datapath mapping |
| `def f(params): return expr` | **Pure local helper** — inlined at call sites; see below |
| `def g(params): stmt; …` | **Void local helper** — body inlined at call sites; see below |

### The segment model and `zdc.tick()`

Each `await` in a `@zdc.proc` loop marks a **cycle boundary**. All
`self.field` assignments between two `await` points form a **segment**
and are lowered to non-blocking assignments in a single FSM state —
they all fire on the same clock edge.

```python
@zdc.proc
async def _count(self):
    while True:
        self.count = self.count + 1   # ─┐ one segment →
        await zdc.tick()              # ─┘  one clock cycle
```

When a loop body has **no blocking port calls**, use `await zdc.tick()`
as the explicit cycle marker. Without it (or some other `await`) the
proc never yields — simulation hangs and synthesis has no cycle boundary.

**Within-segment read-after-write** follows Python sequential semantics:
if you write then read the same field in the same segment, the read sees
the new value. The synthesizer implements this via intermediate wires.

### `zdc.field` vs `zdc.Reg`

| | `zdc.field` | `zdc.Reg` |
|---|---|---|
| Assign in `@zdc.proc` | `self.x = val` — direct, in current segment | `await self.x.write(val)` — bus handshake, new FSM state |
| Use for | proc-owned state (counter, PC, GPR) | memory-mapped control/status registers |



A `def` (or `async def` with no `await`) declared inside a `@zdc.proc`
body is treated as a **pure local helper** and is automatically inlined
at every call site during IR construction.

Rules:
- The function body may contain `return expr` (return the expression) or
  a sequence of assignments / `self.field` writes with no explicit return.
- The body may reference the enclosing scope's local variables (closure
  semantics — free variables resolve from the call-site scope).
- Nesting is supported: a local helper may call another local helper
  defined in the same scope.
- A helper that is defined but never called is silently ignored.

```python
@zdc.proc
async def _run(self):
    MASK32 = 0xFFFF_FFFF

    # Pure expression helper — inlined wherever R(idx) appears
    def R(idx): return self.gpr.get(idx) & MASK32
    # Nested helper — calls R, which is also inlined
    def Rs1():  return R(rs1)
    # Void helper — side-effect; inlined as a statement
    def W(rd, v): self.gpr.set(rd, v & MASK32)

    while True:
        rd:  int = dec.rd
        rs1: int = dec.rs1
        result: int = Rs1() + 1   # → self.gpr.get(rs1) & MASK32 + 1
        W(rd, result)              # → self.gpr.set(rd, result & MASK32)
        await self.wait(zdc.Time.ns(1))
```

### Structured return values

Returning a Python `@dataclasses.dataclass` from a plain (non-proc)
method is supported. Attribute access (`dec.field`) lowers to
`ExprAttribute` in the IR, which synthesizes cleanly.

```python
import dataclasses

@dataclasses.dataclass
class DecodeResult:
    opcode: int = 0
    rd:     int = 0
    rs1:    int = 0
    imm_i:  int = 0
    # …

def _decode(self, instr: int) -> DecodeResult:
    return DecodeResult(opcode=instr & 0x7F, rd=(instr >> 7) & 0x1F, …)
```

### Unsupported constructs (raise synthesis errors)

- `dict` / `list` return values from helpers called inside `@zdc.proc`
- `async def` helpers that contain `await` (Phase 2, not yet implemented)
- `for` loops over Python iterables (use `while` with an explicit index)
- `try / except`
- Class instantiation (`SomeClass(…)`) inside `@zdc.proc`
- Calls to methods that are not `@zdc.proc`, ports, or pure local helpers
- `@zdc.proc` loop body with no `await` (proc never yields — use `await zdc.tick()`)
- `await self.reg.write()` for proc-owned state (use direct `self.field = val` instead)
