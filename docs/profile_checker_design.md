# Profile Checker Interface Design (MyPy-based - DEPRECATED)

.. warning::
   **DEPRECATED:** This design document describes the deprecated mypy-based profile checker.
   
   The new IR-based checker (version 2026.1+) uses a different architecture:
   
   * Works with **flake8** instead of mypy
   * Validates the **IR** (Intermediate Representation) instead of Python AST
   * Uses **entrypoints** for registration instead of mypy plugins
   * Provides **accurate source locations** for errors
   
   See :doc:`checker` for the current design.

## Overview

This design defines an extensible checker interface for the zuspec-dataclasses MyPy plugin that allows Profile classes to provide custom validation logic. This enables users to define new profiles with specific rules that MyPy will enforce at type-check time.

## Background

From `profiles.md`, the "Retargetable" category defines rules that should be enforced:
- Elements must have concrete types
- Name-based manipulation is disallowed (hasattr, getattr, setattr)
- Handle enums directly
- Async invocation is instantiation
- All data must be:
  - A width-annotated integer type, string, or float
  - A string
  - A Zuspec-derived class (Struct, Class, Component, etc)
  - A known collection type (list, dict, tuple)
- No infinite-width `int` or untyped `object`

The goal is to make these rules profile-specific and extensible.

## Architecture

### 1. Profile Base Class

Users define profiles by subclassing a `Profile` base class:

```python
# In zuspec/dataclasses/profiles.py
from typing import Optional, Type, Protocol
from mypy.plugin import ClassDefContext, MethodContext, AttributeContext
from mypy.nodes import ClassDef, FuncDef, Expression
from mypy.types import Type as MypyType

class ProfileChecker(Protocol):
    """Protocol that defines the interface for profile-specific checkers.
    
    Users can implement any subset of these methods to customize checking behavior.
    """
    
    def check_class(self, ctx: ClassDefContext) -> None:
        """Called when a class decorated with @dataclass(profile=...) is analyzed.
        
        Args:
            ctx: MyPy class definition context containing the class being analyzed
        """
        ...
    
    def check_field_type(self, field_name: str, field_type: MypyType, ctx: ClassDefContext) -> None:
        """Check if a field's type is valid for this profile.
        
        Args:
            field_name: Name of the field being checked
            field_type: MyPy type of the field
            ctx: Class definition context
        """
        ...
    
    def check_method(self, method: FuncDef, ctx: ClassDefContext) -> None:
        """Check if a method definition is valid for this profile.
        
        Args:
            method: Method definition being checked
            ctx: Class definition context
        """
        ...
    
    def check_variable_annotation(self, var_name: str, var_type: Optional[MypyType], 
                                  expr: Expression, ctx: ClassDefContext) -> None:
        """Check variable annotations in method bodies.
        
        Args:
            var_name: Variable name
            var_type: Annotated type (None if unannotated)
            expr: Expression being assigned
            ctx: Class definition context
        """
        ...
    
    def check_attribute_access(self, attr_name: str, ctx: AttributeContext) -> None:
        """Check attribute access patterns (e.g., disallow getattr/hasattr).
        
        Args:
            attr_name: Attribute being accessed
            ctx: Attribute access context
        """
        ...
    
    def check_method_call(self, method_name: str, ctx: MethodContext) -> Optional[MypyType]:
        """Check method calls for profile-specific restrictions.
        
        Args:
            method_name: Method being called
            ctx: Method call context
            
        Returns:
            Optionally return a refined type, or None to use default
        """
        ...


class Profile:
    """Base class for defining design abstraction profiles.
    
    A Profile defines a set of rules and constraints that apply to classes
    decorated with @dataclass(profile=MyProfile).
    """
    
    @classmethod
    def get_checker(cls) -> Optional[ProfileChecker]:
        """Return the checker implementation for this profile.
        
        Returns:
            ProfileChecker instance, or None to use default checking
        """
        return None
    
    @classmethod
    def get_name(cls) -> str:
        """Return the canonical name for this profile."""
        return cls.__name__
```

### 2. Built-in Profiles

Define standard profiles with their checkers:

```python
# In zuspec/dataclasses/profiles.py (continued)

class PythonProfile(Profile):
    """Permissive profile for pure-Python runtime.
    
    Allows all Python constructs without restrictions.
    """
    
    @classmethod
    def get_checker(cls) -> Optional[ProfileChecker]:
        # No restrictions
        return None


class RetargetableChecker(ProfileChecker):
    """Checker for retargetable code that can be compiled to different targets."""
    
    def check_field_type(self, field_name: str, field_type: MypyType, ctx: ClassDefContext) -> None:
        """Enforce that field types are concrete and retargetable."""
        from mypy.types import Instance, UnionType, AnyType
        
        # Check for infinite-width int
        if isinstance(field_type, Instance):
            if field_type.type.fullname == 'builtins.int':
                ctx.api.fail(
                    f"Field '{field_name}' uses infinite-width 'int'. "
                    f"Use width-annotated types (uint8_t, uint32_t, etc.) for retargetable code",
                    ctx.cls
                )
        
        # Check for object type
        if isinstance(field_type, AnyType):
            ctx.api.fail(
                f"Field '{field_name}' has type 'Any' or 'object'. "
                f"Retargetable code requires concrete types",
                ctx.cls
            )
    
    def check_method_call(self, method_name: str, ctx: MethodContext) -> Optional[MypyType]:
        """Disallow name-based manipulation functions."""
        if method_name in ('hasattr', 'getattr', 'setattr', 'delattr'):
            ctx.api.fail(
                f"Name-based manipulation ('{method_name}') is not allowed in retargetable code. "
                f"All types must be statically known",
                ctx.context
            )
        return None
    
    def check_variable_annotation(self, var_name: str, var_type: Optional[MypyType], 
                                  expr: Expression, ctx: ClassDefContext) -> None:
        """Require type annotations on local variables."""
        if var_type is None:
            ctx.api.fail(
                f"Variable '{var_name}' is not type-annotated. "
                f"Retargetable code requires explicit type annotations",
                expr
            )


class RetargetableProfile(Profile):
    """Profile for retargetable code (ZuspecFull).
    
    Enforces rules for code that can be compiled to multiple targets:
    - No infinite-width integers
    - No untyped objects
    - No dynamic attribute access
    - All variables must be type-annotated
    """
    
    @classmethod
    def get_checker(cls) -> Optional[ProfileChecker]:
        return RetargetableChecker()


# Default profile mapping
DEFAULT_PROFILE = RetargetableProfile
PROFILE_REGISTRY = {
    'Python': PythonProfile,
    'Retargetable': RetargetableProfile,
    'ZuspecFull': RetargetableProfile,  # Alias
}
```

### 3. Decorator Extension

Extend the `@dataclass` decorator to accept a `profile` parameter:

```python
# In zuspec/dataclasses/decorators.py

from typing import Optional, Type
from .profiles import Profile, DEFAULT_PROFILE

@dataclass_transform()
def dataclass(cls=None, *, profile: Optional[Type[Profile]] = None, **kwargs):
    """Decorator for defining zuspec dataclasses with optional profile enforcement.
    
    Args:
        cls: Class being decorated (when used without parameters)
        profile: Profile class defining validation rules (defaults to RetargetableProfile)
        **kwargs: Additional arguments passed to dataclasses.dataclass
    
    Example:
        from zuspec.dataclasses import dataclass, profiles
        
        @dataclass(profile=profiles.PythonProfile)
        class MyClass:
            x: int  # Allowed with Python profile
        
        @dataclass(profile=profiles.RetargetableProfile)
        class MyRetargetableClass:
            x: uint32_t  # Width-annotated type required
    """
    def decorator(cls):
        # Store profile information in class metadata for mypy plugin
        if not hasattr(cls, '__profile__'):
            if profile is None:
                cls.__profile__ = DEFAULT_PROFILE
            else:
                cls.__profile__ = profile
        
        return dc.dataclass(cls, kw_only=True, **kwargs)
    
    # Handle both @dataclass and @dataclass(...) syntax
    if cls is None:
        return decorator
    else:
        return decorator(cls)
```

### 4. MyPy Plugin Integration

Update the MyPy plugin to use profile checkers:

```python
# In zuspec/dataclasses/mypy/plugin.py

from typing import Optional, Dict, Type
from mypy.plugin import Plugin, ClassDefContext, MethodContext, AttributeContext

class ZuspecPlugin(Plugin):
    def __init__(self, options):
        super().__init__(options)
        self._profile_cache: Dict[str, Optional[ProfileChecker]] = {}
    
    def get_class_decorator_hook(self, fullname: str) -> Optional[Callable[[ClassDefContext], None]]:
        if fullname in ('zuspec.dataclasses.decorators.dataclass', 'zuspec.dataclasses.dataclass'):
            return self.check_dataclass_with_profile
        return None
    
    def get_method_hook(self, fullname: str) -> Optional[Callable[[MethodContext], MypyType]]:
        # Check for disallowed functions in retargetable code
        if fullname in ('builtins.hasattr', 'builtins.getattr', 'builtins.setattr', 'builtins.delattr'):
            return self.check_dynamic_attribute_access
        return None
    
    def check_dataclass_with_profile(self, ctx: ClassDefContext) -> None:
        """Check dataclass according to its profile."""
        # Get profile from decorator arguments or class metadata
        profile_checker = self._get_profile_checker(ctx)
        
        if profile_checker is not None:
            # Run profile-specific checks
            if hasattr(profile_checker, 'check_class'):
                profile_checker.check_class(ctx)
            
            # Check each field
            for name, sym in ctx.cls.info.names.items():
                if isinstance(sym.node, Var) and hasattr(sym.node, 'type'):
                    if hasattr(profile_checker, 'check_field_type'):
                        profile_checker.check_field_type(name, sym.node.type, ctx)
            
            # Check methods
            for stmt in ctx.cls.defs.body:
                if isinstance(stmt, (FuncDef, Decorator)):
                    func = stmt.func if isinstance(stmt, Decorator) else stmt
                    if hasattr(profile_checker, 'check_method'):
                        profile_checker.check_method(func, ctx)
        
        # Run existing bind checks (these apply to all profiles)
        self.check_dataclass_bind(ctx)
    
    def _get_profile_checker(self, ctx: ClassDefContext) -> Optional[ProfileChecker]:
        """Extract and cache profile checker for a class."""
        class_fullname = ctx.cls.fullname
        
        if class_fullname in self._profile_cache:
            return self._profile_cache[class_fullname]
        
        # Try to determine profile from decorator call
        profile_checker = self._extract_profile_from_decorator(ctx)
        
        # Cache and return
        self._profile_cache[class_fullname] = profile_checker
        return profile_checker
    
    def _extract_profile_from_decorator(self, ctx: ClassDefContext) -> Optional[ProfileChecker]:
        """Extract profile parameter from @dataclass decorator."""
        # Look for the decorator in the class
        from mypy.nodes import CallExpr, NameExpr, MemberExpr
        
        for decorator in ctx.cls.decorators:
            if isinstance(decorator, CallExpr):
                # Check if this is @dataclass(...) call
                callee_name = None
                if isinstance(decorator.callee, NameExpr):
                    callee_name = decorator.callee.fullname
                elif isinstance(decorator.callee, MemberExpr):
                    callee_name = decorator.callee.fullname
                
                if callee_name in ('zuspec.dataclasses.dataclass', 'zuspec.dataclasses.decorators.dataclass'):
                    # Look for 'profile' keyword argument
                    for i, arg_name in enumerate(decorator.arg_names):
                        if arg_name == 'profile':
                            profile_arg = decorator.args[i]
                            # Try to resolve profile type
                            return self._resolve_profile_checker(profile_arg, ctx)
        
        # No profile specified, use default
        from zuspec.dataclasses.profiles import DEFAULT_PROFILE
        return DEFAULT_PROFILE.get_checker()
    
    def _resolve_profile_checker(self, profile_expr: Expression, ctx: ClassDefContext) -> Optional[ProfileChecker]:
        """Resolve profile expression to a checker instance."""
        # This is called during mypy analysis, so we need to be careful
        # We can check the type of the expression
        if isinstance(profile_expr, NameExpr):
            profile_fullname = profile_expr.fullname
            # Map known profile names to checkers
            from zuspec.dataclasses.profiles import PROFILE_REGISTRY
            
            # Extract class name from fullname
            profile_name = profile_fullname.split('.')[-1] if profile_fullname else None
            
            if profile_name in PROFILE_REGISTRY:
                profile_cls = PROFILE_REGISTRY[profile_name]
                return profile_cls.get_checker()
        
        # Default fallback
        from zuspec.dataclasses.profiles import DEFAULT_PROFILE
        return DEFAULT_PROFILE.get_checker()
    
    def check_dynamic_attribute_access(self, ctx: MethodContext) -> MypyType:
        """Check if dynamic attribute access is allowed in current profile."""
        # Try to determine the profile of the current class context
        # This is more complex as we need to walk up the context
        # For now, apply to all classes (can be refined later)
        
        method_name = ctx.context.callee.name if hasattr(ctx.context, 'callee') else 'unknown'
        
        # Get profile from current class if in method
        # This would require tracking current class context
        # For simplicity, always warn (user can override with Python profile)
        
        return ctx.default_return_type
```

### 5. Usage Examples

#### Example 1: Using Default Retargetable Profile

```python
import zuspec.dataclasses as zdc

@zdc.dataclass  # Uses RetargetableProfile by default
class Counter(zdc.Component):
    count: zdc.uint32_t = zdc.output()
    reset: zdc.uint1_t = zdc.input()
    
    @zdc.sync(clock=lambda s: s.clock)
    def _count(self):
        val: zdc.uint32_t = self.count + 1  # Type annotation required
        self.count = val
        # x = 5  # ERROR: Variable not type-annotated
```

#### Example 2: Permissive Python Profile

```python
import zuspec.dataclasses as zdc
from zuspec.dataclasses import profiles

@zdc.dataclass(profile=profiles.PythonProfile)
class FlexibleModel:
    data: int  # OK: infinite-width int allowed in Python profile
    
    def process(self):
        x = 5  # OK: unannotated variable allowed
        if hasattr(self, 'optional_field'):  # OK: dynamic access allowed
            return getattr(self, 'optional_field')
```

#### Example 3: Custom Profile

```python
from zuspec.dataclasses.profiles import Profile, ProfileChecker, PROFILE_REGISTRY
from mypy.plugin import ClassDefContext
from mypy.types import Type as MypyType

class RestrictedRTLChecker(ProfileChecker):
    """Custom checker for restricted RTL subset."""
    
    def check_field_type(self, field_name: str, field_type: MypyType, ctx: ClassDefContext) -> None:
        # Only allow uint types, no signed integers
        from mypy.types import Instance
        if isinstance(field_type, Instance):
            type_name = field_type.type.fullname
            if 'int' in type_name and type_name.startswith('zuspec.dataclasses.types.'):
                if not type_name.startswith('zuspec.dataclasses.types.uint'):
                    ctx.api.fail(
                        f"Field '{field_name}' uses signed type. "
                        f"RestrictedRTL only allows unsigned types",
                        ctx.cls
                    )
    
    def check_method(self, method: FuncDef, ctx: ClassDefContext) -> None:
        # Disallow async methods in RTL
        if method.is_coroutine:
            ctx.api.fail(
                f"Method '{method.name}' is async. "
                f"RestrictedRTL does not allow async methods",
                method
            )

class RestrictedRTLProfile(Profile):
    """Custom profile for restricted RTL synthesis."""
    
    @classmethod
    def get_checker(cls) -> Optional[ProfileChecker]:
        return RestrictedRTLChecker()

# Register custom profile
PROFILE_REGISTRY['RestrictedRTL'] = RestrictedRTLProfile

# Use custom profile
@zdc.dataclass(profile=RestrictedRTLProfile)
class SimpleCounter(zdc.Component):
    count: zdc.uint8_t = zdc.output()
    # count_signed: zdc.int8_t = zdc.output()  # ERROR: Signed types not allowed
```

## Implementation Plan

1. **Phase 1: Core Infrastructure**
   - Create `zuspec/dataclasses/profiles.py` with base classes
   - Define `Profile` and `ProfileChecker` protocol
   - Implement `PythonProfile` and `RetargetableProfile`

2. **Phase 2: Decorator Integration**
   - Update `@dataclass` decorator to accept `profile` parameter
   - Store profile metadata in class attributes

3. **Phase 3: MyPy Plugin Updates**
   - Refactor plugin to extract profile from decorator
   - Implement checker dispatch mechanism
   - Add profile-specific validation hooks

4. **Phase 4: Testing**
   - Create test cases for each profile
   - Test custom profile creation
   - Validate error messages and locations

5. **Phase 5: Documentation**
   - Document profile system in user guide
   - Provide examples of custom profiles
   - Document ProfileChecker protocol

## Benefits

1. **Extensibility**: Users can define custom profiles for specific needs
2. **Flexibility**: Different parts of codebase can use different profiles
3. **Gradual Migration**: Can start with Python profile and move to Retargetable
4. **Type Safety**: MyPy enforces profile rules at type-check time
5. **Clear Errors**: Profile-specific error messages guide users

## Future Extensions

1. **Profile Composition**: Allow profiles to inherit/compose from others
2. **Plugin-based Checkers**: Load external checker plugins
3. **Runtime Validation**: Optional runtime checking for Python profile
4. **IDE Integration**: Better IDE support for profile-specific hints
5. **Profile Inference**: Automatically infer minimal required profile
