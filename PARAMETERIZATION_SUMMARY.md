# Parameterization Support Summary

## Overview

This document describes the implementation of parameterized types in zuspec-dataclasses, supporting structural type parameters (const fields) with width and kwargs expressions, as demonstrated in `initiator.py`.

## Key Features

### 1. Const Fields (Structural Type Parameters)

Const fields act as compile-time/construction-time parameters that configure types:

```python
@zdc.dataclass
class WishboneInitiator(zdc.Bundle):
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
    # ... fields using these params
```

**Implementation:**
- `zdc.const(default=value)` creates a field with metadata `{"kind": "const"}`
- DataModelFactory marks these fields with `is_const=True` in the IR
- These fields are included in the type's field list and can be referenced by other fields

### 2. Width Expressions with Lambda

Field widths can reference const parameters via lambda expressions:

```python
@zdc.dataclass
class WishboneInitiator(zdc.Bundle):
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    dat_w : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
    sel : zdc.bitv = zdc.input(width=lambda s:int(s.DATA_WIDTH/8))  # Computed widths
```

**Implementation:**
- `input()` and `output()` accept `width=` parameter (int or lambda)
- `field()` also supports `width=` for PackedStruct fields
- Width metadata is stored in field metadata as callable
- DataModelFactory extracts width lambdas into `ExprLambda` in IR field's `width_expr`

### 3. Kwargs for Bundle Instantiation

Components can pass const parameters to nested bundles:

```python
@zdc.dataclass
class InitiatorCore(zdc.Component):
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
    
    init : WishboneInitiator = zdc.bundle(
        kwargs=lambda s:dict(DATA_WIDTH=s.DATA_WIDTH, ADDR_WIDTH=s.ADDR_WIDTH))
```

**Implementation:**
- `bundle()`, `mirror()`, `monitor()`, and `inst()` accept `kwargs=` parameter
- Kwargs can be a dict or lambda returning dict
- DataModelFactory extracts kwargs lambdas into `ExprLambda` in IR field's `kwargs_expr`

### 4. Bundle Base Class

Added `Bundle` base class for interface/port collections:

```python
class Bundle(TypeBase):
    """Bundle base class for interface/port collections with directionality."""
    pass
```

**Usage:**
- Bundles group related signals with directionality (input/output)
- Support parameterization via const fields
- Can be instantiated with `bundle()`, `mirror()`, or `monitor()`

## IR Enhancements

### New Fields in `Field` and `FieldInOut` (ir/fields.py)

```python
@dc.dataclass(kw_only=True)
class Field(Base):
    # ... existing fields ...
    width_expr : Optional[Expr] = dc.field(default=None)
    kwargs_expr : Optional[Expr] = dc.field(default=None)
    is_const : bool = dc.field(default=False)
```

- **`width_expr`**: Stores width lambda as `ExprLambda` for evaluation at instantiation
- **`kwargs_expr`**: Stores kwargs lambda as `ExprLambda` for parameterized instantiation
- **`is_const`**: Boolean flag indicating structural type parameter

### New Expression Type (ir/expr.py)

```python
@dc.dataclass(kw_only=True)
class ExprLambda(Expr):
    """Represents a lambda/callable stored for later evaluation.
    
    Used for width specs and kwargs that reference const fields.
    """
    callable: object = dc.field()  # The actual Python callable
```

## DataModelFactory Updates

The `_extract_fields()` method now:

1. Detects const fields via metadata `{"kind": "const"}` and sets `is_const=True`
2. Extracts width metadata and wraps callables in `ExprLambda`
3. Extracts kwargs metadata and wraps callables in `ExprLambda`
4. Populates `width_expr` and `kwargs_expr` fields in the IR

## Evaluation Semantics

### When are expressions evaluated?

**Design Decision Points:**

1. **Const field defaults**: Evaluated at class definition time (Python dataclass default)
   - Can be overridden at instance construction time

2. **Width lambdas** (`width=lambda s:s.WIDTH`):
   - **Currently**: Stored as-is in IR for later evaluation
   - **Evaluation point**: Should be evaluated when:
     - Creating an instance (runtime construction)
     - Generating backend code (compilation/synthesis)
   - The lambda receives `s` (self/instance) to access const field values

3. **Kwargs lambdas** (`kwargs=lambda s:dict(W=s.WIDTH)`):
   - **Currently**: Stored as-is in IR for later evaluation
   - **Evaluation point**: When constructing nested bundle/component instances
   - The lambda receives `s` (parent instance) to access parent const fields

### Type Specialization Strategy

**Current Approach**: Store lambdas in IR, evaluate at instantiation

**Alternative Approaches Considered**:
- Create specialized concrete types (e.g., `WishboneInitiator_32_32`)
  - Would require template-like instantiation
  - More complex IR but simpler backend code generation
- Store as AST expressions
  - Would require AST-based evaluation engine
  - More flexible but more complex

## Testing

Comprehensive test suite in `tests/unit/test_parameterization.py`:

- ✅ Const field declarations with defaults
- ✅ Width lambdas referencing const fields
- ✅ Kwargs lambdas for bundle instantiation
- ✅ Multiple const parameters
- ✅ Computed widths (e.g., `DATA_WIDTH/8` for byte enables)
- ✅ Nested parameterized bundles
- ✅ Const in PackedStruct
- ✅ DataModelFactory IR extraction of const, width_expr, kwargs_expr
- ✅ Full Wishbone initiator pattern

## Example: Complete Pattern

```python
@zdc.dataclass
class WishboneInitiator(zdc.Bundle):
    # Structural type parameters (const fields)
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
    
    # Parameterized field widths
    adr : zdc.bitv = zdc.output(width=lambda s:s.ADDR_WIDTH)
    dat_w : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
    dat_r : zdc.bitv = zdc.input(width=lambda s:s.DATA_WIDTH)
    sel : zdc.bitv = zdc.input(width=lambda s:int(s.DATA_WIDTH/8))
    
    # Fixed-width signals
    cyc : zdc.bit = zdc.output()
    we : zdc.bit = zdc.output()

@zdc.dataclass
class InitiatorCore(zdc.Component):
    # Component's own parameters
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
    
    # Nested bundle with parameter propagation
    init : WishboneInitiator = zdc.bundle(
        kwargs=lambda s:dict(DATA_WIDTH=s.DATA_WIDTH, ADDR_WIDTH=s.ADDR_WIDTH))
    
    # Nested structs with parameters
    class ReqData(zdc.PackedStruct):
        DATA_WIDTH : zdc.u32 = zdc.const(default=32)
        ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
        adr : zdc.bitv = zdc.field(width=lambda s:s.ADDR_WIDTH)
        dat : zdc.bitv = zdc.field(width=lambda s:s.DATA_WIDTH)
```

## Questions Answered

### 1. Const field evaluation timing?
**Answer**: Defaults are evaluated at class definition time. Values can be overridden at instance construction via kwargs.

### 2. Width lambda evaluation?
**Answer**: Stored as `ExprLambda` in IR. Should be evaluated at:
- Instance construction time (runtime)
- Code generation time (backend synthesis)

### 3. Kwargs propagation?
**Answer**: Stored as `ExprLambda` in IR. Evaluated when constructing nested instances, receiving parent instance as context.

### 4. Type specialization in IR?
**Answer**: Using lambda storage approach - store callables in IR, evaluate at instantiation. This provides flexibility for different backends and use cases without pre-specializing types.

## Future Enhancements

Potential improvements:

1. **Default const propagation**: Automatically propagate parent const defaults to nested bundles
2. **Type specialization cache**: Cache specialized type instances for performance
3. **Width inference**: Infer widths from const field types
4. **Backend-specific evaluation**: Different evaluation strategies for simulation vs synthesis
5. **AST-based width expressions**: Convert lambdas to AST for more flexible manipulation

## Backward Compatibility

All changes are backward compatible:
- Existing tests pass without modification
- New fields in IR have default values
- Bundle base class is new, doesn't affect existing Component usage
- Width/kwargs parameters are optional
