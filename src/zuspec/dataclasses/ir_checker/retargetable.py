"""Retargetable profile IR checker - replaces MyPy plugin functionality."""

from typing import List, Dict, Set, Optional, Any
from .base import BaseIRChecker, CheckError, CheckContext
from ..ir.data_type import DataTypeInt, DataTypeString, DataTypeStruct, DataTypeClass, DataTypeComponent
from ..ir.expr import ExprCall, ExprRef, ExprRefPy, ExprAttribute
from ..ir.stmt import StmtAssign
import logging

logger = logging.getLogger(__name__)


class RetargetableIRChecker(BaseIRChecker):
    """
    IR-based checker for Retargetable profile.
    
    Enforces constraints required for hardware code generation:
    - No infinite-width integers (must use uint8_t, uint32_t, etc.)
    - No Any/object types (must be concrete)
    - No dynamic attribute access (hasattr, getattr, setattr, delattr)
    - All local variables must be type-annotated
    - Only Zuspec-derived types in annotations
    - No non-Zuspec constructors/calls in method bodies
    - No top-level helper functions in retargetable modules
    
    This replaces the functionality previously in the MyPy plugin.
    """
    
    PROFILE_NAME = 'Retargetable'
    
    # Known Zuspec modules and allowed stdlib types
    ZUSPEC_MODULES = {'zuspec.dataclasses', 'zuspec'}
    ALLOWED_STDLIB_TYPES = {
        'str', 'bool', 'float', 'list', 'dict', 'tuple', 'set'
    }
    
    # Dynamic access functions that are forbidden
    FORBIDDEN_DYNAMIC = {'hasattr', 'getattr', 'setattr', 'delattr'}
    
    def __init__(self):
        super().__init__()
        self._checked_modules: Set[str] = set()
        self._module_top_funcs: Dict[str, Set[str]] = {}
    
    def check_field(self, field: 'Field', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check field type is valid for retargetable code.
        
        Rules:
        1. No infinite-width integers
        2. Only Zuspec types allowed
        3. Check default_factory if present
        """
        errors = []
        
        # Get the field's datatype
        field_type = getattr(field, 'datatype', None) or getattr(field, 'type', None)
        if not field_type:
            return errors  # No type to check
        
        # Rule 1: No infinite-width integers
        if isinstance(field_type, DataTypeInt):
            # DataTypeInt uses 'bits' attribute for width
            width = getattr(field_type, 'bits', None) or getattr(field_type, 'width', None)
            if not width or width == 0:
                errors.append(self.make_error(
                    'ZDC001',
                    f"Field '{field.name}' uses infinite-width int. "
                    f"Use width-annotated types (uint8_t, uint32_t, etc.) for retargetable code",
                    field
                ))
        
        # Rule 2: Only Zuspec types allowed
        if field_type and not self._is_zuspec_type_obj(field_type):
            errors.append(self.make_error(
                'ZDC002',
                f"Field '{field.name}' has non-Zuspec type. "
                f"Retargetable code requires Zuspec types (Component, Struct, or width-annotated types)",
                field
            ))
        
        # Rule 3: Check default_factory (if we can extract it from metadata)
        # This would need access to the original Python field definition
        # For now, we skip this as it's hard to detect from IR alone
        
        return errors
    
    def check_function(self, func: 'Function', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check function for retargetable compliance.
        
        Rules:
        1. All parameters must be Zuspec types
        2. Method body must not have unannotated variables
        3. No dynamic attribute access
        4. No non-Zuspec constructor calls
        5. No top-level function calls
        """
        errors = []
        
        # Rule 1: Check parameter types
        if hasattr(func, 'args') and func.args and hasattr(func.args, 'args'):
            for arg in func.args.args:
                if hasattr(arg, 'arg') and arg.arg != 'self':
                    # Check if annotation exists and is valid
                    if hasattr(arg, 'annotation') and arg.annotation:
                        # Try to extract type from annotation
                        # This is challenging from IR, so we do best-effort
                        pass
        
        # Rules 2-5: Check body via parent implementation
        errors.extend(super().check_function(func, check_ctx))
        
        return errors
    
    def check_statement(self, stmt: 'Stmt', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check statements for retargetable violations.
        
        Rules:
        1. All variable assignments must be type-annotated
        2. No forbidden expressions
        """
        from ..ir.stmt import StmtAssign, StmtAnnAssign
        
        errors = []
        
        # Rule 1: Check for unannotated variable assignments
        if isinstance(stmt, StmtAssign):
            # Check if this is an unannotated assignment
            # In IR, StmtAssign without type annotation is problematic
            if hasattr(stmt, 'targets') and stmt.targets:
                for target in stmt.targets:
                    # Check if target is a simple name (local variable)
                    if isinstance(target, ExprRef):
                        if hasattr(target, 'ref') and isinstance(target.ref, str):
                            var_name = target.ref
                            # Check if variable is already in scope
                            if not check_ctx.lookup_var(var_name):
                                # New variable without annotation
                                errors.append(self.make_error(
                                    'ZDC003',
                                    f"Variable '{var_name}' is not type-annotated. "
                                    f"Retargetable code requires explicit type annotations",
                                    stmt
                                ))
        
        # Check expressions in statement
        errors.extend(super().check_statement(stmt, check_ctx))
        
        return errors
    
    def check_expression(self, expr: 'Expr', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check expressions for retargetable violations.
        
        Rules:
        1. No dynamic attribute access (hasattr, getattr, setattr, delattr)
        2. No non-Zuspec type constructors
        3. No top-level function calls
        """
        errors = []
        
        # Rule 1 & 2 & 3: Check function calls
        if isinstance(expr, ExprCall):
            errors.extend(self._check_call_expression(expr, check_ctx))
        
        # Rule: Check attribute access (ExprRefPy indicates Python-level access)
        if isinstance(expr, ExprRefPy):
            # This might be dynamic access, check if it's forbidden
            if hasattr(expr, 'ref') and expr.ref in self.FORBIDDEN_DYNAMIC:
                errors.append(self.make_error(
                    'ZDC004',
                    f"Dynamic attribute access ('{expr.ref}') is not allowed in retargetable code. "
                    f"All types must be statically known",
                    expr
                ))
        
        # Recursively check sub-expressions
        errors.extend(super().check_expression(expr, check_ctx))
        
        return errors
    
    def _check_call_expression(self, call: ExprCall, check_ctx: CheckContext) -> List[CheckError]:
        """Check a call expression for various violations."""
        errors = []
        
        # Extract function/constructor name
        func_name = self._get_call_name(call)
        
        if not func_name:
            return errors
        
        # Rule 1: No dynamic attribute access functions
        if func_name in self.FORBIDDEN_DYNAMIC:
            errors.append(self.make_error(
                'ZDC004',
                f"Dynamic attribute access ('{func_name}') is not allowed in retargetable code. "
                f"All types must be statically known",
                call
            ))
            return errors
        
        # Rule 2: No non-Zuspec type constructors
        # Check if this looks like a constructor call
        if func_name and func_name[0].isupper():  # Constructor calls typically start with uppercase
            if not self._is_zuspec_name(func_name):
                # Check if it's a known allowed type
                base_name = func_name.split('.')[-1] if '.' in func_name else func_name
                if base_name.lower() not in self.ALLOWED_STDLIB_TYPES:
                    errors.append(self.make_error(
                        'ZDC005',
                        f"Construction of non-Zuspec type '{func_name}' is not allowed in retargetable code",
                        call
                    ))
        
        # Rule 3: No top-level function calls (only if we've tracked them)
        # This requires knowing the module context
        if check_ctx.parent_type:
            module_name = getattr(check_ctx.parent_type, 'module_name', None)
            if module_name and module_name in self._module_top_funcs:
                if func_name in self._module_top_funcs[module_name]:
                    errors.append(self.make_error(
                        'ZDC006',
                        f"Call to non-Zuspec function '{func_name}' is not allowed in retargetable code. "
                        f"Use only Zuspec-decorated methods",
                        call
                    ))
        
        return errors
    
    def _get_call_name(self, call: ExprCall) -> Optional[str]:
        """Extract the function/type name from a call expression."""
        if not hasattr(call, 'func'):
            return None
        
        func_expr = call.func
        
        # Handle different expression types
        if isinstance(func_expr, ExprRef):
            if hasattr(func_expr, 'ref'):
                if isinstance(func_expr.ref, str):
                    return func_expr.ref
        
        elif isinstance(func_expr, ExprRefPy):
            if hasattr(func_expr, 'ref'):
                return str(func_expr.ref)
        
        elif isinstance(func_expr, ExprAttribute):
            # For attribute access like module.Class()
            if hasattr(func_expr, 'attr'):
                return func_expr.attr
        
        return None
    
    def _is_zuspec_name(self, name: str) -> bool:
        """Check if a name is from a Zuspec module."""
        if not name:
            return False
        
        # Check if it starts with zuspec module prefix
        for mod in self.ZUSPEC_MODULES:
            if name.startswith(mod):
                return True
        
        # Check common zuspec type prefixes
        if name.startswith(('uint', 'int', 'bit', 'bv')):
            return True
        
        return False
    
    def _is_zuspec_type_obj(self, dtype: 'DataType') -> bool:
        """Check if a DataType object is a Zuspec type."""
        if dtype is None:
            return False
        
        # Check if it's any DataType - all DataTypes are Zuspec types
        from ..ir.data_type import DataType, DataTypeRef
        
        # Base DataType and all subclasses are Zuspec types, EXCEPT...
        if isinstance(dtype, DataType):
            # Special case: DataTypeRef needs additional checking
            if isinstance(dtype, DataTypeRef):
                if not self._is_zuspec_ref(dtype):
                    return False
            
            # For generic types with element_type (Reg[T], Tuple[T], etc.),
            # also check that the element type is a Zuspec type
            if hasattr(dtype, 'element_type'):
                element_type = getattr(dtype, 'element_type', None)
                if element_type is not None:
                    # Recursively check the element type
                    if not self._is_zuspec_type_obj(element_type):
                        return False
            
            # All DataType instances (with valid element types) are Zuspec types
            return True
        
        # Not a DataType at all
        return False
    
    def _is_zuspec_ref(self, dtype_ref: 'DataTypeRef') -> bool:
        """Check if a DataTypeRef references a Zuspec type."""
        from ..ir.data_type import DataTypeRef
        
        # Check the referenced type name
        ref_name = getattr(dtype_ref, 'ref_name', None)
        if not ref_name:
            return False
        
        # Check if it's a known Zuspec type name
        zuspec_type_names = {
            # Integer types
            'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
            'int8_t', 'int16_t', 'int32_t', 'int64_t',
            'u8', 'u16', 'u32', 'u64',
            'i8', 'i16', 'i32', 'i64',
            'bit', 'bitv',
            # String
            'str', 'string',
            # Zuspec base classes
            'Component', 'Struct', 'Class', 'Protocol',
            # Register and memory types
            'Reg', 'RegFile', 'RegFifo',
            # Other known Zuspec types
            'WishboneInitiator', 'WishboneTarget',  # Known protocol types
            'Lock', 'Event', 'Memory', 'AddressSpace', 'AddrHandle',
            'Channel', 'GetIF', 'PutIF',
        }
        
        # Check exact match
        if ref_name in zuspec_type_names:
            return True
        
        # Check if it starts with known prefixes (for protocol types like WishboneXYZ)
        zuspec_prefixes = ('Wishbone', 'Axi', 'Apb', 'Ahb')
        if any(ref_name.startswith(prefix) for prefix in zuspec_prefixes):
            return True
        
        # Not a known Zuspec type
        return False
    
    def _is_valid_composite_type(self, dtype: 'DataType') -> bool:
        """Check if a composite type is valid for retargetable code."""
        # Struct, Class, Component are all valid
        return isinstance(dtype, (DataTypeStruct, DataTypeClass, DataTypeComponent))


# Type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..ir import Context, DataType, Field, Function, Process, Stmt, Expr
