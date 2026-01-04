"""Base classes and protocols for IR checker framework."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, runtime_checkable, Any, Dict, Type

# Import IR types
import sys
if sys.version_info >= (3, 8):
    from typing import TYPE_CHECKING
else:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from ..ir import Context, DataType, Field, Function, Process, Stmt, Expr
    from ..ir.base import Loc
else:
    # Runtime imports
    Context = Any
    DataType = Any
    Field = Any
    Function = Any
    Process = Any
    Stmt = Any
    Expr = Any
    Loc = Any


@dataclass
class CheckError:
    """Represents a validation error found during checking."""
    code: str           # Error code (e.g., 'ZDC001', 'ZDC002')
    message: str        # Human-readable error message
    filename: str       # Source file path
    lineno: int         # Line number (1-indexed)
    col_offset: int     # Column offset (0-indexed)
    end_lineno: Optional[int] = None
    end_col_offset: Optional[int] = None
    severity: str = 'error'  # 'error' or 'warning'
    
    def __str__(self) -> str:
        """Format error for display."""
        loc = f"{self.filename}:{self.lineno}:{self.col_offset}"
        return f"{loc}: {self.code}: {self.message}"


@dataclass
class CheckContext:
    """
    Context information during checking - shared state across checker invocations.
    
    This provides common infrastructure that all checkers can use to track
    types, scopes, and validation state.
    """
    parent_type: Optional['DataType'] = None
    current_function: Optional['Function'] = None
    local_vars: Dict[str, 'DataType'] = field(default_factory=dict)  # var_name -> DataType
    field_map: Dict[str, 'Field'] = field(default_factory=dict)  # field_name -> Field
    
    # Stack for nested scopes (for blocks, loops, etc.)
    scope_stack: List[Dict[str, 'DataType']] = field(default_factory=list)
    
    def push_scope(self) -> None:
        """Enter a new scope (e.g., for, while, if block)."""
        self.scope_stack.append(dict(self.local_vars))
    
    def pop_scope(self) -> None:
        """Exit current scope."""
        if self.scope_stack:
            self.local_vars = self.scope_stack.pop()
    
    def add_local(self, name: str, type_: 'DataType') -> None:
        """Add a local variable to current scope."""
        self.local_vars[name] = type_
    
    def lookup_var(self, name: str) -> Optional['DataType']:
        """Look up a variable type in current scope."""
        return self.local_vars.get(name)
    
    def clear(self) -> None:
        """Clear context for a new checking run."""
        self.parent_type = None
        self.current_function = None
        self.local_vars.clear()
        self.field_map.clear()
        self.scope_stack.clear()


@runtime_checkable
class IRProfileChecker(Protocol):
    """
    Protocol for IR-based profile checkers.
    
    External packages implement this protocol to add custom validation rules.
    All methods are optional - implement only what you need.
    
    Each method receives:
    - The IR node to check
    - A CheckContext with shared state
    - Returns a list of CheckErrors
    """
    
    PROFILE_NAME: str  # Must be set by implementation
    
    def check_context(self, context: 'Context', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check entire IR context. Called once per file/module.
        
        Default implementation delegates to check_type for each type.
        Override for cross-type validation.
        """
        ...
    
    def check_type(self, datatype: 'DataType', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check a single DataType (Component, Struct, Class, etc.).
        
        Default implementation delegates to check_field, check_function, etc.
        """
        ...
    
    def check_field(self, field: 'Field', check_ctx: CheckContext) -> List[CheckError]:
        """Check a field within a type."""
        ...
    
    def check_function(self, func: 'Function', check_ctx: CheckContext) -> List[CheckError]:
        """Check a method/function."""
        ...
    
    def check_process(self, proc: 'Process', check_ctx: CheckContext) -> List[CheckError]:
        """Check a @process/@sync/@comb decorated method."""
        ...
    
    def check_statement(self, stmt: 'Stmt', check_ctx: CheckContext) -> List[CheckError]:
        """Check a statement in method body."""
        ...
    
    def check_expression(self, expr: 'Expr', check_ctx: CheckContext) -> List[CheckError]:
        """Check an expression."""
        ...


class BaseIRChecker(ABC):
    """
    Base implementation providing common infrastructure for all checkers.
    
    External packages can subclass this for convenience, or implement
    IRProfileChecker directly for more control.
    
    This class provides:
    - Default traversal logic using visitor pattern
    - Error collection and aggregation
    - Location tracking helpers
    - Common type checking utilities
    """
    
    PROFILE_NAME: str = "Base"  # Override in subclass
    
    def __init__(self):
        self.errors: List[CheckError] = []
    
    def check_context(self, context: 'Context', check_ctx: CheckContext) -> List[CheckError]:
        """
        Default implementation: iterate over all types and check each.
        
        Subclasses can override for cross-type checks.
        """
        from ..ir import Context as IRContext
        
        self.errors = []
        check_ctx.clear()
        
        if hasattr(context, 'type_m'):
            for type_name, datatype in context.type_m.items():
                type_errors = self.check_type(datatype, check_ctx)
                self.errors.extend(type_errors)
        
        return self.errors
    
    def check_type(self, datatype: 'DataType', check_ctx: CheckContext) -> List[CheckError]:
        """
        Default implementation: check all fields, functions, processes.
        
        Subclasses typically override this to add type-specific checks.
        """
        errors = []
        check_ctx.parent_type = datatype
        check_ctx.field_map.clear()
        
        # Check fields
        if hasattr(datatype, 'fields') and datatype.fields:
            for field in datatype.fields:
                check_ctx.field_map[field.name] = field
                errors.extend(self.check_field(field, check_ctx))
        
        # Check functions/methods
        if hasattr(datatype, 'methods') and datatype.methods:
            for func in datatype.methods:
                errors.extend(self.check_function(func, check_ctx))
        
        # Check processes (if separate from methods)
        if hasattr(datatype, 'processes') and datatype.processes:
            for proc in datatype.processes:
                errors.extend(self.check_process(proc, check_ctx))
        
        return errors
    
    def check_field(self, field: 'Field', check_ctx: CheckContext) -> List[CheckError]:
        """Default: no checks. Override in subclass."""
        return []
    
    def check_function(self, func: 'Function', check_ctx: CheckContext) -> List[CheckError]:
        """
        Default implementation: check function body statements.
        
        Subclasses can override to add function-level checks.
        """
        errors = []
        check_ctx.current_function = func
        check_ctx.push_scope()
        
        # Add parameters to scope
        if hasattr(func, 'args') and func.args and hasattr(func.args, 'args'):
            for arg in func.args.args:
                if hasattr(arg, 'annotation') and arg.annotation:
                    # Try to extract type from annotation
                    arg_type = self._expr_to_type(arg.annotation, check_ctx)
                    if arg_type and hasattr(arg, 'arg'):
                        check_ctx.add_local(arg.arg, arg_type)
        
        # Check body
        if hasattr(func, 'body') and func.body:
            for stmt in func.body:
                errors.extend(self.check_statement(stmt, check_ctx))
        
        check_ctx.pop_scope()
        check_ctx.current_function = None
        
        return errors
    
    def check_process(self, proc: 'Process', check_ctx: CheckContext) -> List[CheckError]:
        """Default: processes are similar to functions."""
        # Process has a function field
        if hasattr(proc, 'function') and proc.function:
            return self.check_function(proc.function, check_ctx)
        return []
    
    def check_statement(self, stmt: 'Stmt', check_ctx: CheckContext) -> List[CheckError]:
        """
        Default implementation: recursively check nested statements and expressions.
        
        Subclasses override to add statement-specific checks.
        """
        from ..ir.stmt import (StmtExpr, StmtAssign, StmtIf, StmtFor, StmtWhile,
                                StmtReturn, StmtWith)
        
        errors = []
        
        # Check expressions in statement
        if isinstance(stmt, StmtExpr) and hasattr(stmt, 'value') and stmt.value:
            errors.extend(self.check_expression(stmt.value, check_ctx))
        
        elif isinstance(stmt, StmtAssign):
            # Check targets and value
            if hasattr(stmt, 'targets'):
                for target in stmt.targets:
                    errors.extend(self.check_expression(target, check_ctx))
            if hasattr(stmt, 'value') and stmt.value:
                errors.extend(self.check_expression(stmt.value, check_ctx))
        
        elif isinstance(stmt, StmtReturn) and hasattr(stmt, 'value') and stmt.value:
            errors.extend(self.check_expression(stmt.value, check_ctx))
        
        # Recursively check nested statements
        if isinstance(stmt, (StmtIf, StmtFor, StmtWhile, StmtWith)):
            if hasattr(stmt, 'body') and stmt.body:
                check_ctx.push_scope()
                for nested_stmt in stmt.body:
                    errors.extend(self.check_statement(nested_stmt, check_ctx))
                check_ctx.pop_scope()
            
            # Check else body for if statements
            if isinstance(stmt, StmtIf) and hasattr(stmt, 'orelse') and stmt.orelse:
                check_ctx.push_scope()
                for nested_stmt in stmt.orelse:
                    errors.extend(self.check_statement(nested_stmt, check_ctx))
                check_ctx.pop_scope()
        
        return errors
    
    def check_expression(self, expr: 'Expr', check_ctx: CheckContext) -> List[CheckError]:
        """
        Default: recursively check sub-expressions.
        
        Subclasses should override to add expression-specific checks.
        """
        from ..ir.expr import ExprBin, ExprCall, ExprAttribute
        
        errors = []
        
        # Recursively check sub-expressions
        if isinstance(expr, ExprBin):
            if hasattr(expr, 'left') and expr.left:
                errors.extend(self.check_expression(expr.left, check_ctx))
            if hasattr(expr, 'right') and expr.right:
                errors.extend(self.check_expression(expr.right, check_ctx))
        
        elif isinstance(expr, ExprCall):
            if hasattr(expr, 'func') and expr.func:
                errors.extend(self.check_expression(expr.func, check_ctx))
            if hasattr(expr, 'args') and expr.args:
                for arg in expr.args:
                    errors.extend(self.check_expression(arg, check_ctx))
        
        elif isinstance(expr, ExprAttribute):
            if hasattr(expr, 'value') and expr.value:
                errors.extend(self.check_expression(expr.value, check_ctx))
        
        return errors
    
    # Helper methods for subclasses
    
    def make_error(self, code: str, message: str, node: Any, 
                   severity: str = 'error') -> CheckError:
        """Create a CheckError from an IR node with location info."""
        loc = getattr(node, 'loc', None)
        return CheckError(
            code=code,
            message=message,
            filename=loc.file if loc and hasattr(loc, 'file') and loc.file else '',
            lineno=loc.line if loc and hasattr(loc, 'line') else 1,
            col_offset=loc.pos if loc and hasattr(loc, 'pos') else 0,
            severity=severity
        )
    
    def _expr_to_type(self, expr: 'Expr', check_ctx: CheckContext) -> Optional['DataType']:
        """
        Helper: extract DataType from type annotation expression.
        
        This is best-effort - not all annotations can be resolved to DataType.
        """
        from ..ir.expr import ExprConstant
        
        # If the expression is a constant, it might hold a type reference
        if isinstance(expr, ExprConstant) and hasattr(expr, 'value'):
            # The value might be a DataType or a reference to one
            if hasattr(expr.value, '__class__'):
                # This is a runtime type, try to resolve it
                pass
        
        return None
    
    def is_zuspec_type(self, datatype: 'DataType') -> bool:
        """Check if a type is a Zuspec type (not pure Python)."""
        from ..ir.data_type import (DataTypeInt, DataTypeStruct, DataTypeClass,
                                     DataTypeComponent, DataTypeString, DataTypeExtern)
        
        if datatype is None:
            return False
        
        return isinstance(datatype, (DataTypeInt, DataTypeStruct, 
                                    DataTypeClass, DataTypeComponent, 
                                    DataTypeString, DataTypeExtern))
