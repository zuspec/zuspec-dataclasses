# Parameterization Implementation Complete

## Summary

Successfully implemented support for Zuspec's structural type parameters (const fields) with parameterized field widths and kwargs, as demonstrated in the initiator.py example.

## Changes Made

### 1. Core Infrastructure

**Added Bundle Base Class** (`types.py`)
- New `Bundle(TypeBase)` class for interface/port collections
- Supports parameterization via const fields
- Exported in `__init__.py`

**Enhanced Field Decorators** (`decorators.py`)
- `field()` now accepts `width=` parameter for PackedStruct fields
- `inst()` now accepts `elem_factory=` and `size=` parameters
- All decorators properly store metadata for later IR extraction

### 2. IR Enhancements

**Enhanced Field IR** (`ir/fields.py`)
```python
class Field(Base):
    # ... existing fields ...
    width_expr : Optional[Expr] = None      # Width lambda expression
    kwargs_expr : Optional[Expr] = None     # Kwargs lambda expression
    is_const : bool = False                 # Structural type parameter flag
```

**New Expression Type** (`ir/expr.py`)
```python
class ExprLambda(Expr):
    """Stores lambda/callable for later evaluation"""
    callable: object  # The Python callable
```

### 3. DataModelFactory Updates (`data_model_factory.py`)

**Field Extraction Enhancement**
- Detects const fields via `metadata["kind"] == "const"`
- Extracts width metadata and wraps callables in `ExprLambda`
- Extracts kwargs metadata and wraps callables in `ExprLambda`
- Populates new IR fields: `width_expr`, `kwargs_expr`, `is_const`

## Supported Patterns

### Pattern 1: Const Fields
```python
@zdc.dataclass
class WishboneInitiator(zdc.Bundle):
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
```

### Pattern 2: Parameterized Widths
```python
@zdc.dataclass
class WishboneInitiator(zdc.Bundle):
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    dat_w : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
    sel : zdc.bitv = zdc.input(width=lambda s:int(s.DATA_WIDTH/8))  # Computed
```

### Pattern 3: Kwargs Propagation
```python
@zdc.dataclass
class InitiatorCore(zdc.Component):
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    init : WishboneInitiator = zdc.bundle(
        kwargs=lambda s:dict(DATA_WIDTH=s.DATA_WIDTH))
```

### Pattern 4: PackedStruct Parameterization
```python
@zdc.dataclass
class ReqData(zdc.PackedStruct):
    DATA_WIDTH : zdc.u32 = zdc.const(default=32)
    dat : zdc.bitv = zdc.field(width=lambda s:s.DATA_WIDTH)
```

### Pattern 5: Instance with Element Factory
```python
@zdc.dataclass
class Component(zdc.Component):
    MSG_WIDTH : zdc.u32 = zdc.const(default=32)
    queue : tuple[Message, ...] = zdc.inst(
        elem_factory=lambda s: Message(WIDTH=s.MSG_WIDTH),
        size=4)
```

## Test Coverage

### Basic Functionality (test_parameterization.py - 14 tests)
- ✅ Const field declarations
- ✅ Width lambdas referencing const fields
- ✅ Kwargs lambdas for bundle instantiation
- ✅ Multiple const parameters
- ✅ Computed widths (e.g., `DATA_WIDTH/8`)
- ✅ Nested parameterized bundles
- ✅ Const in PackedStruct
- ✅ Instance with element factory
- ✅ DataModelFactory IR extraction
- ✅ Full Wishbone initiator pattern

### IR Representation (test_parameterization_ir.py - 6 tests)
- ✅ Complete IR field metadata
- ✅ Nested kwargs representation
- ✅ PackedStruct with params
- ✅ Lambda evaluation with mock instances
- ✅ Kwargs evaluation
- ✅ Multiple const types

### Regression Testing
- ✅ All 221 existing unit tests pass
- ✅ No breaking changes to existing functionality

## Design Decisions

### 1. Lambda Storage Approach
**Decision**: Store lambdas as `ExprLambda` in IR for evaluation at instantiation time

**Rationale**:
- Provides flexibility for different backends
- Avoids premature type specialization
- Simpler implementation than AST-based approach
- Allows runtime and compile-time evaluation strategies

### 2. Const Field Representation
**Decision**: Const fields are regular fields with `is_const=True` flag

**Rationale**:
- Leverages existing field infrastructure
- Simple to implement and understand
- Can be referenced by width/kwargs lambdas
- No special type system changes needed

### 3. Width Expression Timing
**Decision**: Store width expressions for evaluation at:
- Instance construction (runtime)
- Code generation (backend synthesis)

**Rationale**:
- Different backends may need different evaluation strategies
- Runtime can use Python evaluation
- Synthesis backends can analyze/optimize

## API Summary

### User-Facing API
```python
# Const fields
WIDTH : zdc.u32 = zdc.const(default=32)

# Width specification
data : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
data : zdc.bitv = zdc.field(width=lambda s:s.WIDTH)

# Kwargs for nested instances
bundle : MyBundle = zdc.bundle(kwargs=lambda s:dict(W=s.WIDTH))
inst : MyType = zdc.inst(kwargs=lambda s:dict(W=s.WIDTH))

# Element factory
queue : tuple[T, ...] = zdc.inst(
    elem_factory=lambda s: T(W=s.WIDTH),
    size=4)
```

### IR Access
```python
factory = DataModelFactory()
context = factory.build(MyType)
type_dm = context.type_m[type_name]

for field in type_dm.fields:
    if field.is_const:
        # This is a structural parameter
        pass
    if field.width_expr:
        # Has parameterized width
        width_lambda = field.width_expr.callable
        width = width_lambda(instance)
    if field.kwargs_expr:
        # Has kwargs for nested instantiation
        kwargs_lambda = field.kwargs_expr.callable
        kwargs_dict = kwargs_lambda(instance)
```

## Files Modified

1. `src/zuspec/dataclasses/types.py` - Added Bundle class
2. `src/zuspec/dataclasses/decorators.py` - Enhanced field(), inst()
3. `src/zuspec/dataclasses/ir/fields.py` - Added width_expr, kwargs_expr, is_const
4. `src/zuspec/dataclasses/ir/expr.py` - Added ExprLambda
5. `src/zuspec/dataclasses/data_model_factory.py` - Extract width/kwargs metadata

## Files Added

1. `tests/unit/test_parameterization.py` - 14 basic tests
2. `tests/unit/test_parameterization_ir.py` - 6 IR tests
3. `PARAMETERIZATION_SUMMARY.md` - Detailed documentation

## Backward Compatibility

✅ **100% Backward Compatible**
- All existing tests pass (221/221)
- New fields have default values (None/False)
- New parameters are optional
- Bundle class is new, doesn't affect existing code

## Future Work

Potential enhancements discussed in PARAMETERIZATION_SUMMARY.md:
1. Default const propagation
2. Type specialization cache
3. Width inference
4. Backend-specific evaluation strategies
5. AST-based width expressions
