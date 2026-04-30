# Core Constructs (`zuspec.dataclasses`)

These constructs appear at every abstraction level.

## `@zdc.dataclass`

Required decorator on every Zuspec class. Applies dataclass-style field
processing and registers the class with the Zuspec data model.

## `zdc.Component`

Primary structural building block. Components form hierarchical trees;
child component instances are created automatically for fields of
`Component` type.

```python
@zdc.dataclass
class MyBlock(zdc.Component):
    clk: zdc.bit = zdc.input()
    rst: zdc.bit = zdc.input()
```

- Declare ports with `zdc.input()` / `zdc.output()`
- Declare child components with `zdc.field()` (or `zdc.inst()`)
- Override `__bind__()` to wire ports between children

## Fields and Ports

| Decorator | Role |
|---|---|
| `zdc.input()` | Drives a value into the component |
| `zdc.output()` | Exposes a value from the component |
| `zdc.field()` | Sub-component instance or data field |
| `zdc.port()` | Initiator side of an interface connection |
| `zdc.export()` | Target side of an interface connection |
| `zdc.reg()` | Register-backed field |
| `zdc.array()` | Array field |

## Binding (`__bind__`)

Port connections are expressed as a `dict` mapping returned from
`__bind__()`, or inline via the `bind=` argument to `zdc.field()`.

```python
def __bind__(self): return {
    self.child.clk: self.clk,
    self.child.rst: self.rst,
}
```

**Inline form** — use `zdc.bind[Self, Child]` with a lambda:

```python
child: Child = zdc.field(bind=zdc.bind[Self, Child](lambda s, f: {
    f.clk: s.clk,
    f.rst: s.rst,
}))
```

**Hierarchical binding** — a parent's `__bind__` can also bind child ports
to grandchild ports. Alternatively, pass the interface by reference after
elaboration (see `docs/components.rst`).

### Memory / RegFile in `__bind__`

```python
def __bind__(self): return {
    self.aspace.mmap: (
        zdc.At(0x0000_0000, self.mem),
        zdc.At(0x1000_0000, self.regs),
    )
}
```

## Scalar Types

Fixed-width integers: `zdc.u8`, `zdc.u16`, `zdc.u32`, `zdc.u64`,
`zdc.i8` … `zdc.i64`, `zdc.bit`.  
Parameterized: `zdc.bv[N]` / `zdc.bitv[N]`.

## `zdc.Struct` / `zdc.PackedStruct`

Plain data aggregates for passing structured values between components or
across interfaces.

## `zdc.enum`

Decorator for defining Zuspec-aware enumeration types used in constraints
and fields.
