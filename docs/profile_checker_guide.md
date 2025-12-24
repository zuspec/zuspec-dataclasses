# Profile Checker User Guide

## Overview

The zuspec-dataclasses profile checker system allows you to define and enforce different validation rules for your dataclasses. Profiles enable you to specify what Python constructs are allowed, ensuring your code meets specific requirements (e.g., hardware synthesis, code generation to other languages).

## Built-in Profiles

### PythonProfile

The `PythonProfile` is permissive and allows all Python constructs without restrictions.

**Use when:**
- Writing pure Python implementations
- Prototyping before targeting hardware
- Need maximum flexibility

**Allows:**
- Infinite-width integers (`int`)
- Dynamic attribute access (`hasattr`, `getattr`, `setattr`)
- Unannotated variables
- `Any` and `object` types

**Example:**
```python
import zuspec.dataclasses as zdc
from zuspec.dataclasses import profiles

@zdc.dataclass(profile=profiles.PythonProfile)
class FlexibleModel:
    count: int = zdc.field(default=0)  # infinite-width int OK
    
    def process(self):
        x = 5  # unannotated variable OK
        if hasattr(self, 'optional'):  # dynamic access OK
            return getattr(self, 'optional')
```

### RetargetableProfile (Default)

The `RetargetableProfile` is the default profile and enforces rules for code that can be compiled to multiple targets (Verilog, VHDL, C++, etc.).

**Use when:**
- Writing hardware-targetable code
- Code will be synthesized or compiled
- Need to ensure type safety

**Requires:**
- Width-annotated integer types (`uint8_t`, `uint32_t`, etc.)
- Concrete types (no `Any` or `object`)
- Type annotations on all variables in process/comb/sync methods
- Static attribute access (no `hasattr`, `getattr`, etc.)

**Example:**
```python
import zuspec.dataclasses as zdc

@zdc.dataclass  # Uses RetargetableProfile by default
class Counter(zdc.Component):
    count: zdc.uint32_t = zdc.output()
    
    @zdc.sync(clock=lambda s: s.clock)
    def _count(self):
        next_val: zdc.uint32_t = self.count + 1  # annotation required
        self.count = next_val
```

### ZuspecFull

`ZuspecFull` is an alias for `RetargetableProfile`.

## Creating Custom Profiles

You can create custom profiles to enforce your own rules.

### Step 1: Create a Checker Class

Define a checker class that implements the validation methods you need:

```python
from zuspec.dataclasses.profiles import Profile, ProfileChecker
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mypy.plugin import ClassDefContext, MethodContext
    from mypy.nodes import FuncDef, Expression
    from mypy.types import Type as MypyType


class MyCustomChecker:
    """Custom checker with your validation rules."""
    
    def check_field_type(self, field_name: str, field_type: 'MypyType', 
                        ctx: 'ClassDefContext') -> None:
        """Validate field types."""
        # Your validation logic here
        pass
    
    def check_method(self, method: 'FuncDef', ctx: 'ClassDefContext') -> None:
        """Validate methods."""
        # Your validation logic here
        pass
    
    def check_variable_annotation(self, var_name: str, var_type: Optional['MypyType'], 
                                  expr: 'Expression', ctx: 'ClassDefContext') -> None:
        """Validate variable annotations."""
        # Your validation logic here
        pass
    
    def check_method_call(self, method_name: str, ctx: 'MethodContext') -> Optional['MypyType']:
        """Validate method calls."""
        # Your validation logic here
        return None
```

### Step 2: Create a Profile Class

Create a profile class that returns your checker:

```python
class MyCustomProfile(Profile):
    """My custom profile description."""
    
    @classmethod
    def get_checker(cls) -> Optional[ProfileChecker]:
        return MyCustomChecker()  # type: ignore
```

### Step 3: Register Your Profile (Optional)

Register your profile for easy reference:

```python
from zuspec.dataclasses.profiles import PROFILE_REGISTRY

PROFILE_REGISTRY['MyCustom'] = MyCustomProfile
```

### Step 4: Use Your Profile

Apply your profile to dataclasses:

```python
@zdc.dataclass(profile=MyCustomProfile)
class MyClass:
    # Your class definition
    pass
```

## Complete Custom Profile Example

Here's a complete example of a custom profile that only allows unsigned integer types:

```python
import zuspec.dataclasses as zdc
from zuspec.dataclasses.profiles import Profile, PROFILE_REGISTRY
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mypy.plugin import ClassDefContext
    from mypy.nodes import FuncDef, Expression
    from mypy.types import Type as MypyType


class UnsignedOnlyChecker:
    """Only allow unsigned integer types."""
    
    def check_field_type(self, field_name: str, field_type: 'MypyType', 
                        ctx: 'ClassDefContext') -> None:
        from mypy.types import Instance
        
        if isinstance(field_type, Instance):
            type_name = field_type.type.fullname
            
            # Check if it's a signed integer type
            if type_name.startswith('zuspec.dataclasses.types.int'):
                if not type_name.startswith('zuspec.dataclasses.types.uint'):
                    ctx.api.fail(
                        f"Field '{field_name}' uses signed type. "
                        f"Only unsigned types allowed",
                        ctx.cls
                    )


class UnsignedOnlyProfile(Profile):
    """Profile that only allows unsigned integer types."""
    
    @classmethod
    def get_checker(cls):
        return UnsignedOnlyChecker()  # type: ignore


# Register the profile
PROFILE_REGISTRY['UnsignedOnly'] = UnsignedOnlyProfile


# Use the profile
@zdc.dataclass(profile=UnsignedOnlyProfile)
class MyCounter(zdc.Component):
    count: zdc.uint32_t = zdc.output()  # OK
    # signed_count: zdc.int32_t = zdc.output()  # Would fail MyPy check
```

## Checker Interface

The `ProfileChecker` protocol defines the following methods (all optional):

### check_class(ctx: ClassDefContext)

Called when a class with your profile is analyzed. Use for class-level validation.

### check_field_type(field_name: str, field_type: MypyType, ctx: ClassDefContext)

Called for each field in the class. Use to validate field types.

**Parameters:**
- `field_name`: Name of the field
- `field_type`: MyPy type of the field
- `ctx`: Class definition context

### check_method(method: FuncDef, ctx: ClassDefContext)

Called for each method in the class. Use to validate method definitions.

**Parameters:**
- `method`: Method definition
- `ctx`: Class definition context

### check_variable_annotation(var_name: str, var_type: Optional[MypyType], expr: Expression, ctx: ClassDefContext)

Called for variable assignments in method bodies. Use to enforce annotation requirements.

**Parameters:**
- `var_name`: Variable name
- `var_type`: Annotated type (None if unannotated)
- `expr`: Expression being assigned
- `ctx`: Class definition context

### check_method_call(method_name: str, ctx: MethodContext) -> Optional[MypyType]

Called for method/function calls. Use to restrict certain operations.

**Parameters:**
- `method_name`: Name of method being called
- `ctx`: Method call context

**Returns:** Optionally return a refined type, or None to use default

## MyPy Integration

The profile checker runs as a MyPy plugin. To enable it, add to your `pyproject.toml`:

```toml
[tool.mypy]
plugins = ["zuspec.dataclasses.mypy.plugin"]
```

Or use the `--config-file` option:

```bash
mypy --config-file packages/zuspec-dataclasses/pyproject.toml your_file.py
```

## Error Messages

Profile checkers produce clear error messages:

```
error: Field 'count' uses infinite-width 'int'.
       Use width-annotated types (uint8_t, uint32_t, etc.) for retargetable code

error: Variable 'x' is not type-annotated.
       Retargetable code requires explicit type annotations

error: Name-based manipulation ('hasattr') is not allowed in retargetable code.
       All types must be statically known
```

## Best Practices

1. **Start with PythonProfile** for prototyping, then move to RetargetableProfile
2. **Use TYPE_CHECKING** to avoid runtime dependencies on MyPy
3. **Provide helpful error messages** that explain what's wrong and how to fix it
4. **Test your profile** with both valid and invalid code
5. **Document your profile** so users know what rules apply
6. **Register your profile** in PROFILE_REGISTRY for discoverability

## Profile Composition

While profiles don't currently support inheritance, you can compose checkers:

```python
class ComposedChecker:
    def __init__(self):
        self.checker1 = Checker1()
        self.checker2 = Checker2()
    
    def check_field_type(self, field_name, field_type, ctx):
        self.checker1.check_field_type(field_name, field_type, ctx)
        self.checker2.check_field_type(field_name, field_type, ctx)
```

## Troubleshooting

### Profile not being applied

- Ensure MyPy plugin is configured in `pyproject.toml`
- Check that you're passing the profile class, not an instance
- Verify the profile is registered if using by name

### Checker methods not being called

- Ensure method signatures match the protocol exactly
- Check for exceptions in your checker (they're caught silently)
- Verify MyPy is using the correct config file

### Type checking issues in checker

- Use `TYPE_CHECKING` to avoid runtime imports
- Use string annotations: `'MypyType'` instead of `MypyType`
- Add `# type: ignore` where needed for protocol compatibility

## See Also

- [Profile Checker Design Document](profile_checker_design.md) - Implementation details
- [Profiles Documentation](profiles.md) - Design abstraction levels
- [Complete Example](../examples/profile_example.py) - Working example code
