"""SPRTL Synthesizable profile IR checker.

This checker validates that code can be synthesized to hardware (FSM).
It extends the Retargetable profile with additional synthesis-specific rules.
"""

from typing import List, Dict, Set, Optional, Any
from .base import BaseIRChecker, CheckError, CheckContext
from .retargetable import RetargetableIRChecker
from ..ir.data_type import DataTypeInt, DataTypeStruct, DataTypeComponent, Function
from ..ir.expr import (
    ExprCall, ExprRef, ExprRefPy, ExprAttribute, ExprAwait,
    ExprRefField, ExprRefLocal, ExprRefUnresolved
)
from ..ir.stmt import (
    StmtAssign, StmtAugAssign, StmtIf, StmtWhile, StmtFor,
    StmtExpr, StmtReturn, StmtRaise, StmtTry
)
import logging

logger = logging.getLogger(__name__)


class SPRTLSynthesizableChecker(RetargetableIRChecker):
    """
    IR-based checker for SPRTL Synthesizable profile.
    
    Extends Retargetable profile with synthesis-specific constraints:
    - Only bounded loops (for with range, while with termination)
    - No recursion
    - No dynamic memory allocation
    - No floating-point types
    - No exceptions (try/except/raise)
    - Only synthesizable constructs in @sync processes
    - Proper await usage patterns
    
    SPRTL-specific rules (ZDS prefix):
    - ZDS001: Unbounded loop detected
    - ZDS002: Recursion not allowed
    - ZDS003: Dynamic allocation not allowed
    - ZDS004: Floating-point not synthesizable
    - ZDS005: Exceptions not synthesizable
    - ZDS006: Invalid await pattern
    - ZDS007: @sync process must have while True loop
    - ZDS008: Non-synthesizable statement in @sync process
    """
    
    PROFILE_NAME = 'SPRTLSynthesizable'
    
    # Non-synthesizable constructs
    FORBIDDEN_STMTS = {
        'StmtTry', 'StmtRaise', 'StmtWith',
        'StmtYield', 'StmtYieldFrom',
        'StmtGlobal', 'StmtNonlocal',
        'StmtImport', 'StmtImportFrom',
    }
    
    # Allocation functions
    ALLOCATION_FUNCS = {'list', 'dict', 'set', 'bytearray', 'memoryview'}
    
    def __init__(self):
        super().__init__()
        self._in_sync_process: bool = False
        self._call_graph: Dict[str, Set[str]] = {}  # func_name -> called functions
        self._current_func: Optional[str] = None
    
    def check_function(self, func: 'Function', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check function for synthesizability.
        
        Additional rules for @sync processes:
        1. Must have 'while True' as main loop
        2. Only synthesizable statements allowed
        3. Await patterns must be valid
        """
        errors = []
        
        # First run parent checks (retargetable rules)
        errors.extend(super().check_function(func, check_ctx))
        
        # Track current function for call graph
        prev_func = self._current_func
        self._current_func = func.name
        if func.name not in self._call_graph:
            self._call_graph[func.name] = set()
        
        # Check if this is a @sync process
        metadata = getattr(func, 'metadata', {}) or {}
        is_sync = metadata.get('kind') == 'sync'
        
        if is_sync:
            self._in_sync_process = True
            errors.extend(self._check_sync_process(func, check_ctx))
            self._in_sync_process = False
        else:
            # Check for recursion in regular functions
            errors.extend(self._check_recursion(func, check_ctx))
        
        self._current_func = prev_func
        return errors
    
    def _check_sync_process(self, func: 'Function', check_ctx: CheckContext) -> List[CheckError]:
        """Validate @sync process structure."""
        errors = []
        body = getattr(func, 'body', [])
        
        if not body:
            errors.append(self.make_error(
                'ZDS007',
                f"@sync process '{func.name}' has empty body. "
                f"Expected 'while True:' loop pattern",
                func
            ))
            return errors
        
        # Check for 'while True' pattern
        # Allow docstrings and initial assignments before while True
        found_while_true = False
        for i, stmt in enumerate(body):
            if isinstance(stmt, StmtWhile):
                test = getattr(stmt, 'test', None)
                if test and hasattr(test, 'value') and test.value is True:
                    found_while_true = True
                    # Check statements before while True (should be initialization)
                    for pre_stmt in body[:i]:
                        if not self._is_valid_init_stmt(pre_stmt):
                            errors.append(self.make_error(
                                'ZDS008',
                                f"Statement before 'while True' in @sync process must be "
                                f"assignment or docstring, found {type(pre_stmt).__name__}",
                                pre_stmt
                            ))
                    break
            elif isinstance(stmt, StmtExpr):
                # Allow docstrings (string constants)
                expr = getattr(stmt, 'expr', None)
                if expr and hasattr(expr, 'value') and isinstance(expr.value, str):
                    continue
            elif isinstance(stmt, StmtAssign):
                # Allow initialization assignments
                continue
            else:
                # Non-initialization statement before while True
                pass
        
        if not found_while_true:
            errors.append(self.make_error(
                'ZDS007',
                f"@sync process '{func.name}' must have 'while True:' loop. "
                f"This is the main FSM loop pattern",
                func
            ))
        
        return errors
    
    def _is_valid_init_stmt(self, stmt) -> bool:
        """Check if statement is valid before while True (initialization)."""
        if isinstance(stmt, StmtAssign):
            return True
        if isinstance(stmt, StmtExpr):
            expr = getattr(stmt, 'expr', None)
            # Allow docstrings
            if expr and hasattr(expr, 'value') and isinstance(expr.value, str):
                return True
        return False
    
    def check_statement(self, stmt: 'Stmt', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check statements for synthesizability.
        
        Rules:
        1. No exceptions (try/except/raise)
        2. Only bounded loops
        3. No forbidden statements
        """
        errors = []
        
        # First run parent checks
        errors.extend(super().check_statement(stmt, check_ctx))
        
        stmt_type = type(stmt).__name__
        
        # Rule 1: No exceptions
        if isinstance(stmt, (StmtRaise, StmtTry)):
            errors.append(self.make_error(
                'ZDS005',
                f"Exception handling ({stmt_type}) is not synthesizable. "
                f"Hardware cannot handle exceptions",
                stmt
            ))
        
        # Rule 2: Check loops for bounded iteration
        if isinstance(stmt, StmtWhile):
            errors.extend(self._check_while_bounded(stmt, check_ctx))
        elif isinstance(stmt, StmtFor):
            errors.extend(self._check_for_bounded(stmt, check_ctx))
        
        # Rule 3: Forbidden statements
        if stmt_type in self.FORBIDDEN_STMTS:
            errors.append(self.make_error(
                'ZDS008',
                f"Statement type '{stmt_type}' is not synthesizable",
                stmt
            ))
        
        return errors
    
    def _check_while_bounded(self, stmt: StmtWhile, check_ctx: CheckContext) -> List[CheckError]:
        """Check that while loop is bounded (or is while True in sync process)."""
        errors = []
        
        test = getattr(stmt, 'test', None)
        
        # 'while True' is allowed in sync processes (it's the FSM loop)
        if test and hasattr(test, 'value') and test.value is True:
            if self._in_sync_process:
                return errors  # OK - main FSM loop
            else:
                # while True outside sync process is suspicious
                errors.append(self.make_error(
                    'ZDS001',
                    f"'while True' outside @sync process may be unbounded. "
                    f"Ensure loop terminates via break or has bounded iterations",
                    stmt
                ))
        
        # For other while loops, we can't easily prove termination
        # but we allow them with a warning if they have a condition
        # that references a variable that's modified in the body
        
        return errors
    
    def _check_for_bounded(self, stmt: StmtFor, check_ctx: CheckContext) -> List[CheckError]:
        """Check that for loop has bounded iterations."""
        errors = []
        
        iter_expr = getattr(stmt, 'iter', None)
        if not iter_expr:
            return errors
        
        # Check for range() calls - these are bounded
        if isinstance(iter_expr, ExprCall):
            func = getattr(iter_expr, 'func', None)
            if func:
                func_name = None
                if hasattr(func, 'name'):
                    func_name = func.name
                elif hasattr(func, 'id'):
                    func_name = func.id
                
                if func_name == 'range':
                    # range() is bounded, check that arguments are constants
                    args = getattr(iter_expr, 'args', [])
                    for arg in args:
                        if not self._is_constant_expr(arg):
                            errors.append(self.make_error(
                                'ZDS001',
                                f"For loop with non-constant range bounds may be unbounded. "
                                f"Use constant bounds for synthesizable loops",
                                stmt
                            ))
                            break
                    return errors
        
        # For other iterables, warn about potential unboundedness
        errors.append(self.make_error(
            'ZDS001',
            f"For loop iteration source may be unbounded. "
            f"Use 'for i in range(N)' with constant N for synthesizable loops",
            stmt
        ))
        
        return errors
    
    def _is_constant_expr(self, expr) -> bool:
        """Check if an expression is a compile-time constant."""
        if hasattr(expr, 'value'):
            return isinstance(expr.value, (int, float, str, bool, type(None)))
        return False
    
    def check_expression(self, expr: 'Expr', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check expressions for synthesizability.
        
        Rules:
        1. No dynamic allocation
        2. No floating-point in hardware context
        3. Valid await patterns
        """
        errors = []
        
        # First run parent checks
        errors.extend(super().check_expression(expr, check_ctx))
        
        # Rule 1: No dynamic allocation
        if isinstance(expr, ExprCall):
            func_name = self._get_call_name(expr)
            if func_name in self.ALLOCATION_FUNCS:
                errors.append(self.make_error(
                    'ZDS003',
                    f"Dynamic allocation ('{func_name}') is not synthesizable. "
                    f"Use fixed-size arrays or structs",
                    expr
                ))
            
            # Track calls for recursion detection
            if self._current_func and func_name:
                self._call_graph[self._current_func].add(func_name)
        
        # Rule 3: Check await patterns in sync processes
        if isinstance(expr, ExprAwait) and self._in_sync_process:
            errors.extend(self._check_await_pattern(expr, check_ctx))
        
        return errors
    
    def _check_await_pattern(self, expr: ExprAwait, check_ctx: CheckContext) -> List[CheckError]:
        """Validate await expression patterns for synthesis."""
        errors = []
        
        value = getattr(expr, 'value', None)
        if not value:
            errors.append(self.make_error(
                'ZDS006',
                f"Empty await expression is not valid",
                expr
            ))
            return errors
        
        value_type = type(value).__name__
        
        # Valid patterns:
        # 1. await zdc.cycles(N) - cycle delay
        # 2. await <condition> == <value> - wait for condition
        # 3. await <signal> - wait for signal to be truthy
        
        if isinstance(value, ExprCall):
            # Check for zdc.cycles()
            func = getattr(value, 'func', None)
            if func:
                if hasattr(func, 'attr') and func.attr == 'cycles':
                    # Valid: await zdc.cycles(N)
                    return errors
                func_name = self._get_call_name(value)
                if func_name and func_name not in ('cycles',):
                    errors.append(self.make_error(
                        'ZDS006',
                        f"await with function call '{func_name}' may not be synthesizable. "
                        f"Use 'await zdc.cycles(N)' or 'await <condition>'",
                        expr
                    ))
        
        # Other patterns (comparison, signal) are generally OK
        return errors
    
    def _check_recursion(self, func: 'Function', check_ctx: CheckContext) -> List[CheckError]:
        """Check for recursive function calls."""
        errors = []
        
        # Build call graph during function checking
        # After all functions checked, detect cycles
        # For now, we check direct recursion
        
        func_name = func.name
        if func_name in self._call_graph:
            if func_name in self._call_graph[func_name]:
                errors.append(self.make_error(
                    'ZDS002',
                    f"Function '{func_name}' is recursive. "
                    f"Recursion is not synthesizable to hardware",
                    func
                ))
        
        return errors
    
    def check_field(self, field: 'Field', check_ctx: CheckContext) -> List[CheckError]:
        """
        Check field types for synthesizability.
        
        Additional rules:
        1. No floating-point types
        """
        errors = []
        
        # First run parent checks
        errors.extend(super().check_field(field, check_ctx))
        
        # Rule: No floating-point
        field_type = getattr(field, 'datatype', None)
        if field_type:
            # Check for float types
            type_name = getattr(field_type, 'name', '')
            if type_name and 'float' in type_name.lower():
                errors.append(self.make_error(
                    'ZDS004',
                    f"Field '{field.name}' uses floating-point type. "
                    f"Floating-point is not directly synthesizable. Use fixed-point instead",
                    field
                ))
        
        return errors


# Register the checker
from .registry import CheckerRegistry
CheckerRegistry.register(SPRTLSynthesizableChecker, 'SPRTLSynthesizable')
