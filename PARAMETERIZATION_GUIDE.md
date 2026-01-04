# Parameterization Quick Reference

## Overview

Zuspec supports structural type parameters via `const` fields, enabling reusable parameterized hardware interfaces and components.

## Basic Usage

### 1. Declare Const Parameters

```python
@zdc.dataclass
class MyBundle(zdc.Bundle):
    # Structural parameters with defaults
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    ADDR_WIDTH : zdc.u32 = zdc.const(default=64)
```

### 2. Reference Parameters in Width Specifications

```python
@zdc.dataclass
class MyBundle(zdc.Bundle):
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    
    # Simple reference
    data : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
    
    # Computed width
    strobe : zdc.bitv = zdc.output(width=lambda s:int(s.DATA_WIDTH/8))
```

### 3. Pass Parameters to Nested Bundles

```python
@zdc.dataclass
class MyComponent(zdc.Component):
    BUS_WIDTH : zdc.u32 = zdc.const(default=32)
    
    # Propagate parameter to nested bundle
    bus : MyBundle = zdc.bundle(
        kwargs=lambda s:dict(DATA_WIDTH=s.BUS_WIDTH))
```

## Complete Example

```python
import zuspec.dataclasses as zdc

@zdc.dataclass
class AXI4Lite(zdc.Bundle):
    """Parameterized AXI4-Lite interface"""
    ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    
    # Address write channel
    awaddr  : zdc.bitv = zdc.output(width=lambda s:s.ADDR_WIDTH)
    awvalid : zdc.bit = zdc.output()
    awready : zdc.bit = zdc.input()
    
    # Write data channel
    wdata   : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
    wstrb   : zdc.bitv = zdc.output(width=lambda s:int(s.DATA_WIDTH/8))
    wvalid  : zdc.bit = zdc.output()
    wready  : zdc.bit = zdc.input()
    
    # Write response channel
    bresp   : zdc.bitv = zdc.input(width=2)
    bvalid  : zdc.bit = zdc.input()
    bready  : zdc.bit = zdc.output()

@zdc.dataclass
class AXI4LiteInitiator(zdc.Component):
    """AXI4-Lite initiator with configurable bus width"""
    BUS_ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
    BUS_DATA_WIDTH : zdc.u32 = zdc.const(default=64)
    
    # Instantiate parameterized interface
    axi : AXI4Lite = zdc.bundle(
        kwargs=lambda s:dict(
            ADDR_WIDTH=s.BUS_ADDR_WIDTH,
            DATA_WIDTH=s.BUS_DATA_WIDTH))
```

## Advanced Patterns

### PackedStruct with Parameters

```python
@zdc.dataclass
class Transaction(zdc.PackedStruct):
    """Parameterized transaction struct"""
    ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    
    addr : zdc.bitv = zdc.field(width=lambda s:s.ADDR_WIDTH)
    data : zdc.bitv = zdc.field(width=lambda s:s.DATA_WIDTH)
    valid : zdc.bit = zdc.field()
```

### Multiple Parameterized Instances

```python
@zdc.dataclass
class MultiPortComponent(zdc.Component):
    """Component with multiple buses of different widths"""
    NARROW_WIDTH : zdc.u32 = zdc.const(default=32)
    WIDE_WIDTH : zdc.u32 = zdc.const(default=128)
    
    narrow_bus : DataBus = zdc.bundle(
        kwargs=lambda s:dict(WIDTH=s.NARROW_WIDTH))
    
    wide_bus : DataBus = zdc.bundle(
        kwargs=lambda s:dict(WIDTH=s.WIDE_WIDTH))
```

### Parameterized Arrays

```python
@zdc.dataclass
class QueueComponent(zdc.Component):
    MSG_WIDTH : zdc.u32 = zdc.const(default=64)
    QUEUE_DEPTH : zdc.u32 = zdc.const(default=16)
    
    # Tuple with element factory
    queue : tuple[Message, ...] = zdc.tuple(
        size=lambda s:s.QUEUE_DEPTH,
        elem_factory=lambda s: Message(WIDTH=s.MSG_WIDTH))
```

## Common Patterns

### 1. Bus Width Parameterization
```python
DATA_WIDTH : zdc.u32 = zdc.const(default=32)
data : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
```

### 2. Byte Enable Width (DATA_WIDTH / 8)
```python
DATA_WIDTH : zdc.u32 = zdc.const(default=32)
strobe : zdc.bitv = zdc.output(width=lambda s:int(s.DATA_WIDTH/8))
```

### 3. Address Width Parameterization
```python
ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
addr : zdc.bitv = zdc.output(width=lambda s:s.ADDR_WIDTH)
```

### 4. Parameter Propagation
```python
# Parent
PARAM : zdc.u32 = zdc.const(default=X)
child : ChildType = zdc.bundle(kwargs=lambda s:dict(PARAM=s.PARAM))
```

## Best Practices

### 1. Naming Conventions
- Use UPPER_CASE for const parameter names
- Use descriptive names (DATA_WIDTH, not just WIDTH)
- Add _WIDTH suffix for width parameters

### 2. Default Values
- Always provide sensible defaults
- Use powers of 2 for width defaults
- Document expected ranges

### 3. Width Expressions
- Keep lambda expressions simple
- Use `int()` for division to ensure integer result
- Validate widths make sense (e.g., DATA_WIDTH/8 ≥ 1)

### 4. Documentation
```python
@zdc.dataclass
class MyBundle(zdc.Bundle):
    """Short description
    
    Parameters:
        DATA_WIDTH: Width of data bus (default: 32, range: 8-1024)
        ADDR_WIDTH: Width of address bus (default: 32, range: 16-64)
    """
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
```

## Type Reference

### Available in Bundles/Components
- `zdc.const(default=value)` - Structural parameter
- `zdc.output(width=...)` - Output port with width
- `zdc.input(width=...)` - Input port with width
- `zdc.bundle(kwargs=...)` - Bundle instance with parameters
- `zdc.mirror(kwargs=...)` - Mirrored bundle instance
- `zdc.monitor(kwargs=...)` - Monitor bundle instance

### Available in PackedStruct
- `zdc.const(default=value)` - Structural parameter
- `zdc.field(width=...)` - Field with parameterized width

### Available for Instances
- `zdc.inst(kwargs=...)` - Component instance with parameters
- `zdc.tuple(elem_factory=..., size=...)` - Parameterized array

## Troubleshooting

### Width Expression Not Working
**Problem**: Width lambda not being evaluated
**Solution**: Ensure you're using `lambda s:s.PARAM_NAME` syntax

### Kwargs Not Propagating
**Problem**: Nested bundle has wrong parameter values
**Solution**: Check kwargs lambda returns dict with correct keys

### Type Error in Width Computation
**Problem**: `TypeError: 'float' object cannot be interpreted as an integer`
**Solution**: Wrap division in `int()`: `width=lambda s:int(s.DATA_WIDTH/8)`

## See Also

- `PARAMETERIZATION_SUMMARY.md` - Detailed implementation documentation
- `tests/unit/test_parameterization.py` - Usage examples
- `tests/unit/test_parameterization_ir.py` - IR access examples
