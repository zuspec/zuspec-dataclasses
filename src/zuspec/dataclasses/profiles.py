#****************************************************************************
# Copyright 2019-2025 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
"""
Design abstraction profiles for zuspec dataclasses.

Profiles define validation rules that MyPy enforces at type-check time.
"""
from typing import Optional, Type, Protocol, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mypy.plugin import ClassDefContext, MethodContext, AttributeContext
    from mypy.nodes import FuncDef, Expression, Block, CallExpr
    from mypy.types import Type as MypyType


class ProfileChecker(Protocol):
    """Protocol that defines the interface for profile-specific checkers.
    
    Users can implement any subset of these methods to customize checking behavior.
    Each method is called by the MyPy plugin during type analysis.
    """
    
    def check_class(self, ctx: 'ClassDefContext') -> None:
        """Called when a class decorated with @dataclass(profile=...) is analyzed.
        
        Args:
            ctx: MyPy class definition context containing the class being analyzed
        """
        ...
    
    def check_field_type(self, field_name: str, field_type: 'MypyType', 
                        ctx: 'ClassDefContext', field_node: Optional[Any] = None) -> None:
        """Check if a field's type is valid for this profile.
        
        Args:
            field_name: Name of the field being checked
            field_type: MyPy type of the field
            ctx: Class definition context
            field_node: Optional Var node for the field (for better error location)
        """
        ...
    
    def check_method(self, method: 'FuncDef', ctx: 'ClassDefContext') -> None:
        """Check if a method definition is valid for this profile.
        
        Args:
            method: Method definition being checked
            ctx: Class definition context
        """
        ...
    
    def check_variable_annotation(self, var_name: str, var_type: Optional['MypyType'], 
                                  expr: 'Expression', ctx: 'ClassDefContext') -> None:
        """Check variable annotations in method bodies.
        
        Args:
            var_name: Variable name
            var_type: Annotated type (None if unannotated)
            expr: Expression being assigned
            ctx: Class definition context
        """
        ...
    
    def check_method_call(self, method_name: str, ctx: 'MethodContext') -> Optional['MypyType']:
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
    
    To create a custom profile:
    1. Subclass Profile
    2. Implement get_checker() to return your ProfileChecker implementation
    3. Use @dataclass(profile=YourProfile) on classes
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


class PythonProfile(Profile):
    """Permissive profile for pure-Python runtime.
    
    Allows all Python constructs without restrictions:
    - Infinite-width integers
    - Dynamic attribute access (hasattr, getattr, etc.)
    - Unannotated variables
    - Any/object types
    
    Use this profile for pure Python implementations that won't be compiled
    to other targets.
    """
    
    @classmethod
    def get_checker(cls) -> Optional[ProfileChecker]:
        # No restrictions - use default MyPy behavior
        return None
    
    @classmethod
    def get_name(cls) -> str:
        """Return the canonical name without 'Profile' suffix."""
        return 'Python'


class RetargetableChecker:
    """Checker for retargetable code that can be compiled to different targets.
    
    Enforces constraints required for code generation:
    - No infinite-width integers (must use uint8_t, uint32_t, etc.)
    - No Any/object types (must be concrete)
    - No dynamic attribute access (hasattr, getattr, setattr, delattr)
    - All local variables must be type-annotated
    - Only Zuspec-derived types in annotations
    - No non-Zuspec constructors/calls in method bodies
    - No top-level helper functions (eg my_f) in retargetable modules
    """

    def _span_for(self, ctx_obj: Any, text: str) -> Any:
        """Return a mypy.nodes.Context spanning the full token text."""
        from mypy.nodes import Context

        c = Context()
        try:
            c.set_line(ctx_obj)
        except Exception:
            c.line = int(getattr(ctx_obj, 'line', -1) or -1)
            c.column = int(getattr(ctx_obj, 'column', -1) or -1)

        end_line = getattr(ctx_obj, 'end_line', None)
        end_col = getattr(ctx_obj, 'end_column', None)

        c.end_line = c.line if end_line is None else int(end_line)
        c.end_column = c.column if end_col is None else int(end_col)

        # Always ensure we cover the full token; mypy sometimes sets end_column
        # to a single character for some contexts.
        if c.end_line == c.line:
            want_end = c.column + len(text)
            if c.end_column is None or c.end_column < want_end:
                c.end_column = want_end

        return c

    _checked_modules: set[str] = set()
    _module_top_funcs: Dict[str, set[str]] = {}
    
    # Known Zuspec base classes and allowed stdlib types
    ZUSPEC_MODULES = {'zuspec.dataclasses', 'zuspec'}
    ALLOWED_STDLIB_TYPES = {
        'builtins.str', 'builtins.bool', 'builtins.float',
        'builtins.list', 'builtins.dict', 'builtins.tuple', 'builtins.set',
        'typing.List', 'typing.Dict', 'typing.Tuple', 'typing.Set',
        'typing.Protocol', 'typing.Optional', 'typing.Union'
    }

    def check_class(self, ctx: 'ClassDefContext') -> None:
        """Track top-level functions in modules with retargetable classes."""
        modname = ctx.cls.info.module_name
        if modname in self._checked_modules:
            return
        self._checked_modules.add(modname)

        # Track top-level functions for later checking at call sites.
        # Top-level functions are considered regular Python and are only
        # flagged if called from within a Zuspec-decorated retargetable method.
        try:
            mod = ctx.api.modules.get(modname)
        except Exception:
            mod = None
        
        if not mod:
            return
        
        from mypy.nodes import FuncDef
        top_funcs: set[str] = set()
        for d in getattr(mod, 'defs', []):
            if isinstance(d, FuncDef):
                # Ignore dunder helpers
                if d.name.startswith('__'):
                    continue
                top_funcs.add(d.name)
        self._module_top_funcs[modname] = top_funcs

    def _is_zuspec_derived(self, type_fullname: str) -> bool:
        """Check if a type is Zuspec-derived or allowed."""
        # Check if it's from zuspec modules
        for mod in self.ZUSPEC_MODULES:
            if type_fullname.startswith(mod):
                return True
        
        # Check if it's an allowed stdlib type
        if type_fullname in self.ALLOWED_STDLIB_TYPES:
            return True
        
        return False

    def _resolve_name_to_typeinfo(self, name: str, ctx: 'ClassDefContext', where: Any) -> Optional[Any]:
        """Resolve a name to a TypeInfo using mypy's symbol lookup."""
        sym = None
        try:
            if '.' in name and hasattr(ctx.api, 'lookup_fully_qualified'):
                sym = ctx.api.lookup_fully_qualified(name)
            else:
                sym = ctx.api.lookup_qualified(name, where, suppress_errors=True)
        except Exception:
            sym = None

        if sym and hasattr(sym, 'node'):
            from mypy.nodes import TypeInfo
            if isinstance(sym.node, TypeInfo):
                return sym.node
        return None
    
    def check_field_type(self, field_name: str, field_type: 'MypyType',
                        ctx: 'ClassDefContext', field_node: Optional[Any] = None) -> None:
        """Enforce that field types are concrete and retargetable."""
        from mypy.types import Instance, AnyType, UnboundType
        
        # Prefer marking the type token itself (better underline span)
        error_context = field_type if field_type is not None else (field_node if field_node is not None else ctx.cls)
        
        # Check if this is an UnboundType (pre-resolution type expression)
        if isinstance(field_type, UnboundType):
            # UnboundType.name contains the original name like 'zdc.uint32_t' or 'int'
            type_name = field_type.name if hasattr(field_type, 'name') else ''
            
            # Allow zuspec annotated types
            if 'uint' in type_name or ('int' in type_name and ('8' in type_name or '16' in type_name or '32' in type_name or '64' in type_name)):
                # This is a zuspec annotated type like uint32_t, int8_t, etc.
                return
            
            # Check for bare 'int' which is infinite-width
            if type_name == 'int' or type_name == 'builtins.int':
                ctx.api.fail(
                    f"Field '{field_name}' uses infinite-width 'int'. "
                    f"Use width-annotated types (uint8_t, uint32_t, etc.) for retargetable code",
                    error_context
                )
                return
            
            # Check if it's a non-Zuspec type (same logic as _check_type_annotation)
            if not any(type_name.startswith(mod) for mod in ['zdc.', 'zuspec.', 'typing.', 'builtins.']):
                # Check if it's defined in the same module (likely Zuspec-derived)
                if '.' not in type_name:
                    # Might be a class in the same module - we'll check it as Instance later
                    pass
                else:
                    ctx.api.fail(
                        f"Field '{field_name}' has type '{type_name}' which is not Zuspec-derived. "
                        f"Retargetable code requires Zuspec types",
                        self._span_for(error_context, type_name)
                    )
                    return
        
        # Check for infinite-width int (resolved type)
        if isinstance(field_type, Instance):
            type_fullname = field_type.type.fullname
            
            if type_fullname == 'builtins.int':
                # This is a resolved int type
                ctx.api.fail(
                    f"Field '{field_name}' uses infinite-width 'int'. "
                    f"Use width-annotated types (uint8_t, uint32_t, etc.) for retargetable code",
                    error_context
                )
                return
            
            # Check if it's a non-Zuspec-derived class
            if not self._is_zuspec_derived(type_fullname):
                # Check if it's a zuspec dataclass by looking for decorators
                if not self._is_decorated_with_zuspec_dataclass(field_type.type):
                    ctx.api.fail(
                        f"Field '{field_name}' has type '{type_fullname}' which is not Zuspec-derived. "
                        f"Retargetable code requires Zuspec types (Struct, Component, etc.)",
                        self._span_for(error_context, type_fullname.split('.')[-1])
                    )
        
        # Check for Any/object type
        if isinstance(field_type, AnyType):
            ctx.api.fail(
                f"Field '{field_name}' has type 'Any' or 'object'. "
                f"Retargetable code requires concrete types",
                error_context
            )

        # Also validate zdc.field(default_factory=...) for retargetable code
        try:
            from mypy.nodes import AssignmentStmt, CallExpr, NameExpr, MemberExpr
            if isinstance(field_node, AssignmentStmt) and isinstance(field_node.rvalue, CallExpr):
                call = field_node.rvalue
                callee_name = None
                if isinstance(call.callee, NameExpr):
                    callee_name = call.callee.name
                elif isinstance(call.callee, MemberExpr):
                    callee_name = call.callee.name

                if callee_name == 'field':
                    for i, arg_name in enumerate(call.arg_names):
                        if arg_name == 'default_factory':
                            self.check_field_default_factory(field_name, call.args[i], ctx, field_node)
        except Exception:
            pass
    
    def check_field_default_factory(self, field_name: str, default_factory_expr: Any,
                                   ctx: 'ClassDefContext', field_node: Optional[Any] = None) -> None:
        """Ensure default_factory classes are usable in retargetable code."""
        from mypy.nodes import NameExpr, MemberExpr

        if not isinstance(default_factory_expr, (NameExpr, MemberExpr)):
            return

        factory_fullname = getattr(default_factory_expr, 'fullname', None)
        if not factory_fullname:
            return

        # Allow stdlib factories for stdlib container types
        if factory_fullname in (
            'builtins.list', 'builtins.dict', 'builtins.set', 'builtins.tuple',
        ):
            return

        # Allow Input/Output markers (used internally to infer signal kind)
        if factory_fullname in (
            'zuspec.dataclasses.decorators.Input',
            'zuspec.dataclasses.decorators.Output',
            'zuspec.dataclasses.Input',
            'zuspec.dataclasses.Output',
        ):
            return

        # Resolve to a TypeInfo (must be a class)
        type_info = None
        try:
            from mypy.types import Instance
            inst = ctx.api.named_type(factory_fullname)
            if isinstance(inst, Instance):
                type_info = inst.type
        except Exception:
            type_info = self._resolve_name_to_typeinfo(
                factory_fullname,
                ctx,
                field_node if field_node is not None else ctx.cls
            )

        if type_info is None:
            return

        # Require that the factory class inherits from a Zuspec base type
        zuspec_bases = (
            'zuspec.dataclasses.types.Component',
            'zuspec.dataclasses.types.Struct',
            'zuspec.dataclasses.types.RegFile',
            'zuspec.dataclasses.types.AddressSpace',
        )

        if hasattr(type_info, 'mro'):
            for base in type_info.mro:
                if getattr(base, 'fullname', '') in zuspec_bases:
                    return

        err_ctx = default_factory_expr if default_factory_expr is not None else (field_node if field_node is not None else ctx.cls)
        ctx.api.fail(
            f"Field '{field_name}' has default_factory '{factory_fullname}' which does not inherit from a Zuspec type. "+
            f"Retargetable code requires default_factory classes to inherit from zuspec.dataclasses types",
            err_ctx
        )


    def _is_decorated_with_zuspec_dataclass(self, type_info: Any) -> bool:
        """Check if a type is decorated with @zdc.dataclass."""
        if hasattr(type_info, 'metadata'):
            # Check if the class has zuspec metadata
            if 'zuspec_fields' in type_info.metadata:
                return True
        
        # Check if any base class is from zuspec
        if hasattr(type_info, 'mro'):
            for base in type_info.mro:
                if base.fullname.startswith('zuspec.dataclasses'):
                    return True
        
        return False
    
    def check_method(self, method: 'FuncDef', ctx: 'ClassDefContext') -> None:
        """Check method for retargetable compliance."""
        # Check method parameters for non-Zuspec types
        if hasattr(method, 'arguments') and method.arguments:
            for arg in method.arguments:
                if arg.variable and arg.variable.type:
                    # Prefer marking the type annotation expression (better span)
                    err_ctx = arg.type_annotation if getattr(arg, 'type_annotation', None) is not None else arg
                    self._check_type_annotation(
                        arg.variable.name,
                        arg.variable.type,
                        err_ctx,
                        ctx
                    )
        
        # Check for forbidden constructs in method body
        if method.body:
            self._check_method_body_for_dynamic_access(method.body, ctx)
    
    def _check_type_annotation(self, param_name: str, param_type: 'MypyType',
                               node: Any, ctx: 'ClassDefContext') -> None:
        """Check if a type annotation is valid for retargetable code."""
        from mypy.types import Instance, UnboundType
        
        # Allow 'self' parameter
        if param_name == 'self':
            return
        
        # Check UnboundType (pre-resolution)
        if isinstance(param_type, UnboundType):
            type_name = param_type.name if hasattr(param_type, 'name') else ''
            
            # Allow zuspec types and stdlib types
            if any(type_name.startswith(mod) for mod in ['zdc.', 'zuspec.', 'typing.', 'builtins.']):
                return
            
            # For unqualified names, try to resolve to a TypeInfo now (best-effort)
            if '.' not in type_name and type_name:
                ti = self._resolve_name_to_typeinfo(type_name, ctx, node)
                if ti is not None:
                    if not self._is_zuspec_derived(ti.fullname) and not self._is_decorated_with_zuspec_dataclass(ti):
                        ctx.api.fail(
                            f"Parameter '{param_name}' has type '{ti.fullname}' which is not Zuspec-derived. "
                            f"Retargetable code requires Zuspec types",
                            self._span_for(node, ti.name)
                        )
                    return
            
            # Qualified name that's not from a known module
            if '.' in type_name:
                ctx.api.fail(
                    f"Parameter '{param_name}' has type '{type_name}' which is not Zuspec-derived. "
                    f"Retargetable code requires Zuspec types",
                    self._span_for(param_type, type_name.split('.')[-1] if type_name else 'type')
                )
                return
        
        # Check resolved Instance type
        if isinstance(param_type, Instance):
            type_fullname = param_type.type.fullname
            
            # Check if it's a non-Zuspec-derived class
            if not self._is_zuspec_derived(type_fullname):
                # Check if it's decorated with @zdc.dataclass
                if not self._is_decorated_with_zuspec_dataclass(param_type.type):
                    ctx.api.fail(
                        f"Parameter '{param_name}' has type '{type_fullname}' which is not Zuspec-derived. "
                        f"Retargetable code requires Zuspec types",
                        self._span_for(node, type_fullname.split('.')[-1])
                    )
    
    def _check_method_body_for_dynamic_access(self, block: 'Block', ctx: 'ClassDefContext') -> None:
        """Check method body for dynamic attribute access (getattr, setattr, hasattr, delattr)."""
        from mypy.nodes import (Block, CallExpr, NameExpr, IfStmt, WhileStmt, ForStmt, WithStmt, 
                                ExpressionStmt, ReturnStmt, AssignmentStmt)
        
        for stmt in block.body:
            # Check expression statements that might contain calls
            if isinstance(stmt, ExpressionStmt):
                if isinstance(stmt.expr, CallExpr):
                    self._check_call_for_dynamic_access(stmt.expr, ctx)
                # Also recursively check the expression tree
                self._check_expr_for_dynamic_access(stmt.expr, ctx)
            
            # Check return statements
            elif isinstance(stmt, ReturnStmt):
                if stmt.expr:
                    self._check_expr_for_dynamic_access(stmt.expr, ctx)
            
            # Check assignment statements
            elif isinstance(stmt, AssignmentStmt):
                if stmt.rvalue:
                    self._check_expr_for_dynamic_access(stmt.rvalue, ctx)
            
            # Check call expressions directly (shouldn't happen but be safe)
            elif isinstance(stmt, CallExpr):
                self._check_call_for_dynamic_access(stmt, ctx)
            
            # Recursively check nested blocks
            elif isinstance(stmt, IfStmt):
                for body_block in stmt.body:
                    self._check_method_body_for_dynamic_access(body_block, ctx)
                if stmt.else_body:
                    self._check_method_body_for_dynamic_access(stmt.else_body, ctx)
                # Also check the condition expression
                self._check_expr_for_dynamic_access(stmt.expr[0] if stmt.expr else None, ctx)
            
            elif isinstance(stmt, (WhileStmt, ForStmt)):
                self._check_method_body_for_dynamic_access(stmt.body, ctx)
            
            elif isinstance(stmt, WithStmt):
                self._check_method_body_for_dynamic_access(stmt.body, ctx)
    
    def _check_expr_for_dynamic_access(self, expr: Any, ctx: 'ClassDefContext') -> None:
        """Recursively check an expression tree for dynamic attribute access."""
        from mypy.nodes import CallExpr, ComparisonExpr, OpExpr, UnaryExpr
        
        if expr is None:
            return
        
        # Check if this expression is a call to a dynamic function
        if isinstance(expr, CallExpr):
            self._check_call_for_dynamic_access(expr, ctx)
            # Recursively check arguments
            for arg in expr.args:
                self._check_expr_for_dynamic_access(arg, ctx)
        
        # Recursively check comparison expressions
        elif isinstance(expr, ComparisonExpr):
            for operand in expr.operands:
                self._check_expr_for_dynamic_access(operand, ctx)
        
        # Recursively check binary operations
        elif isinstance(expr, OpExpr):
            self._check_expr_for_dynamic_access(expr.left, ctx)
            self._check_expr_for_dynamic_access(expr.right, ctx)
        
        # Recursively check unary operations
        elif isinstance(expr, UnaryExpr):
            self._check_expr_for_dynamic_access(expr.expr, ctx)
    
    def _check_call_for_dynamic_access(self, call: 'CallExpr', ctx: 'ClassDefContext') -> None:
        """Check if a call expression is a forbidden construct."""
        from mypy.nodes import NameExpr, MemberExpr, TypeInfo

        # 1) Dynamic attribute access
        if isinstance(call.callee, NameExpr):
            func_name = call.callee.name
            if func_name in ('getattr', 'setattr', 'hasattr', 'delattr'):
                ctx.api.fail(
                    f"Dynamic attribute access ('{func_name}') is not allowed in retargetable code. "
                    f"All types must be statically known",
                    call
                )
                return

        # 2) Construction/call of non-Zuspec class OR call to non-Zuspec function
        type_fullname: Optional[str] = None
        type_info: Optional[TypeInfo] = None

        if isinstance(call.callee, NameExpr):
            # If this is a class name, mypy often attaches a TypeInfo node
            if isinstance(getattr(call.callee, 'node', None), TypeInfo):
                type_info = call.callee.node
            else:
                # Best-effort scope lookup
                type_info = self._resolve_name_to_typeinfo(call.callee.name, ctx, call)
        elif isinstance(call.callee, MemberExpr):
            # For qualified calls like mod.Object(), fullname may be available
            if getattr(call.callee, 'fullname', None):
                type_fullname = call.callee.fullname

        if type_info is not None:
            type_fullname = type_info.fullname

        if type_fullname and not self._is_zuspec_derived(type_fullname) and not (
            type_info is not None and self._is_decorated_with_zuspec_dataclass(type_info)
        ):
            # Only flag class construction/calls
            if type_info is not None:
                # Prefer underlining the constructor name token
                ctor_tok = type_fullname.split('.')[-1]
                ctx.api.fail(
                    f"Construction of non-Zuspec type '{type_fullname}' is not allowed in retargetable code.",
                    self._span_for(call.callee, ctor_tok)
                )
                return

        # 3) Calls to non-Zuspec top-level functions (eg my_f)
        if isinstance(call.callee, NameExpr):
            modname = ctx.cls.info.module_name
            top_funcs = self._module_top_funcs.get(modname, set())
            if call.callee.name in top_funcs:
                ctx.api.fail(
                    f"Call to non-Zuspec function '{call.callee.name}' is not allowed in retargetable code.",
                    self._span_for(call.callee, call.callee.name)
                )
    
    def check_method_call(self, method_name: str, ctx: 'MethodContext') -> Optional['MypyType']:
        """Disallow name-based manipulation functions."""
        if method_name in ('hasattr', 'getattr', 'setattr', 'delattr'):
            ctx.api.fail(
                f"Name-based manipulation ('{method_name}') is not allowed in retargetable code. "
                f"All types must be statically known",
                ctx.context
            )
        return None
    
    def check_variable_annotation(self, var_name: str, var_type: Optional['MypyType'], 
                                  expr: 'Expression', ctx: 'ClassDefContext') -> None:
        """Require type annotations on local variables in process/comb/sync methods."""
        if var_type is None:
            ctx.api.fail(
                f"Variable '{var_name}' is not type-annotated. "
                f"Retargetable code requires explicit type annotations",
                expr
            )


class RetargetableProfile(Profile):
    """Profile for retargetable code (ZuspecFull).
    
    Enforces rules for code that can be compiled to multiple targets including
    Verilog, VHDL, C++, or other hardware description languages.
    
    Rules:
    - Elements must have concrete types
    - Name-based manipulation is disallowed (hasattr, getattr, etc.)
    - All data must be:
      * A width-annotated integer type (uint8_t, uint32_t, etc.)
      * A string
      * A Zuspec-derived class (Struct, Class, Component, etc.)
      * A known collection type (List, Dict, Tuple with concrete element types)
    - No infinite-width int or untyped object
    - All variables in process/comb/sync methods must be type-annotated
    """
    
    @classmethod
    def get_checker(cls) -> Optional[ProfileChecker]:
        return RetargetableChecker()
    
    @classmethod
    def get_name(cls) -> str:
        """Return the canonical name without 'Profile' suffix."""
        return 'Retargetable'


# Default profile - Retargetable is the default as specified in profiles.md
DEFAULT_PROFILE = RetargetableProfile

# Profile registry for lookup by name
PROFILE_REGISTRY: Dict[str, Type[Profile]] = {
    'Python': PythonProfile,
    'PythonProfile': PythonProfile,
    'Retargetable': RetargetableProfile,
    'RetargetableProfile': RetargetableProfile,
    'ZuspecFull': RetargetableProfile,  # Alias as mentioned in profiles.md
}


def get_profile_by_name(name: str) -> Optional[Type[Profile]]:
    """Look up a profile by name.
    
    Args:
        name: Profile name (e.g., 'Python', 'Retargetable')
        
    Returns:
        Profile class, or None if not found
    """
    return PROFILE_REGISTRY.get(name)


__all__ = [
    'ProfileChecker',
    'Profile',
    'PythonProfile',
    'RetargetableProfile',
    'RetargetableChecker',
    'DEFAULT_PROFILE',
    'PROFILE_REGISTRY',
    'get_profile_by_name',
]
