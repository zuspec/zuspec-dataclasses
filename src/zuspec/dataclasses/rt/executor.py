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
"""Process Execution Engine."""

from __future__ import annotations
import dataclasses as dc
from typing import Any, Optional, TYPE_CHECKING
from ..ir.stmt import Stmt, StmtAssign, StmtIf, StmtPass, StmtExpr
from ..ir.expr import (
    Expr, ExprConstant, ExprRefField, ExprBin, ExprAttribute,
    BinOp, TypeExprRefSelf, ExprRefLocal, ExprRefUnresolved, ExprCall,
    ExprCompare, CmpOp, ExprSubscript, ExprBool, BoolOp
)
from ..ir.expr_phase2 import ExprIfExp
from .eval_state import EvalState

if TYPE_CHECKING:
    from ..types import Component


class Executor:
    """Base class for executing process statements and expressions."""
    
    def __init__(self, state_backend, component: Component):
        """Initialize executor.
        
        Args:
            state_backend: Either EvalState or CompImplRT
            component: Component being evaluated
        """
        self.state_backend = state_backend
        self.component = component
        self.is_deferred = False  # Set to True for sync processes
        self.locals = {}  # Local variable storage
        
        # Check if using EvalState or CompImplRT
        self.use_eval_state = hasattr(state_backend, 'read')  # EvalState has read()
    
    def _read_signal(self, field_path: str) -> Any:
        """Read signal value from backend."""
        if self.use_eval_state:
            return self.state_backend.read(field_path)
        else:
            return self.state_backend.signal_read(self.component, field_path)
    
    def _write_signal(self, field_path: str, value: Any):
        """Write signal value to backend."""
        if self.use_eval_state:
            if self.is_deferred:
                self.state_backend.write_deferred(field_path, value)
            else:
                self.state_backend.write_immediate(field_path, value)
        else:
            self.state_backend.signal_write(self.component, field_path, value)
    
    def execute_stmts(self, stmts: list[Stmt]):
        """Execute a list of statements."""
        for stmt in stmts:
            self.execute_stmt(stmt)
    
    def execute_stmt(self, stmt: Stmt):
        """Execute a single statement."""
        if isinstance(stmt, StmtAssign):
            self.execute_assign(stmt)
        elif isinstance(stmt, StmtIf):
            self.execute_if(stmt)
        elif isinstance(stmt, StmtPass):
            pass  # Do nothing
        elif isinstance(stmt, StmtExpr):
            # Evaluate expression for side effects
            self.evaluate_expr(stmt.expr)
        else:
            raise NotImplementedError(f"Statement type {type(stmt)} not implemented")
    
    def execute_assign(self, stmt: StmtAssign):
        """Execute an assignment statement."""
        # Evaluate RHS
        value = self.evaluate_expr(stmt.value)
        
        # Assign to all targets (usually just one)
        for target in stmt.targets:
            # Check if target is a local variable
            if isinstance(target, ExprRefLocal):
                self.locals[target.name] = value
            elif isinstance(target, ExprSubscript):
                # Handle subscript assignment (e.g., array[index] = value)
                base = self.evaluate_expr(target.value)
                index = self.evaluate_expr(target.slice)
                base[int(index)] = value
            else:
                field_path = self.get_field_path(target)
                self._write_signal(field_path, value)
    
    def execute_if(self, stmt: StmtIf):
        """Execute an if statement."""
        # Evaluate condition
        test_value = self.evaluate_expr(stmt.test)
        
        if test_value:
            self.execute_stmts(stmt.body)
        else:
            self.execute_stmts(stmt.orelse)
    
    def evaluate_expr(self, expr: Expr) -> Any:
        """Evaluate an expression and return its value."""
        if expr is None:
            return None
        
        if isinstance(expr, ExprConstant):
            return expr.value
        
        elif isinstance(expr, ExprRefLocal):
            # Reference to local variable
            return self.locals.get(expr.name, 0)
        
        elif isinstance(expr, ExprRefField):
            field_path = self.get_field_path(expr)
            return self._read_signal(field_path)
        
        elif isinstance(expr, ExprBin):
            left = self.evaluate_expr(expr.lhs)
            right = self.evaluate_expr(expr.rhs)
            return self.apply_binop(expr.op, left, right)
        
        elif isinstance(expr, TypeExprRefSelf):
            # Reference to self - return None (handled by ExprAttribute)
            return None
        
        elif isinstance(expr, ExprAttribute):
            # Prefer interpreting attribute access as a signal path (eg io.req)
            if not self.use_eval_state:
                try:
                    field_path = self.get_field_path(expr)
                    return self._read_signal(field_path)
                except Exception:
                    pass

            # Handle self.field_name or method calls
            base = self.evaluate_expr(expr.value)
            if base is None and isinstance(expr.value, TypeExprRefSelf):
                # This is self.attr - could be field, method, or Python attribute
                # First check if it's a Python attribute (from __post_init__)
                if hasattr(self.component, expr.attr):
                    attr_value = getattr(self.component, expr.attr)
                    if callable(attr_value):
                        return attr_value
                    # If it's a non-callable attribute (e.g., list, dict), return it directly
                    if not isinstance(attr_value, (int, float, str, bool, type(None))):
                        return attr_value
                # Otherwise try to read as signal
                return self._read_signal(expr.attr)
            return getattr(base, expr.attr, 0)
        
        elif isinstance(expr, ExprRefUnresolved):
            # Unresolved reference - try to resolve from module globals
            # This handles references to constants like ALU_ADD
            import sys
            frame = sys._getframe()
            while frame:
                if expr.name in frame.f_locals:
                    return frame.f_locals[expr.name]
                if expr.name in frame.f_globals:
                    return frame.f_globals[expr.name]
                frame = frame.f_back
            # Try component's module
            if hasattr(self.component, '__module__'):
                mod = sys.modules.get(self.component.__module__)
                if mod and hasattr(mod, expr.name):
                    return getattr(mod, expr.name)
            return 0  # Default if not found
        
        elif isinstance(expr, ExprCall):
            # Handle function/method calls
            func = self.evaluate_expr(expr.func)
            args = [self.evaluate_expr(arg) for arg in expr.args]
            kwargs = {kw.arg: self.evaluate_expr(kw.value) for kw in expr.keywords}
            if callable(func):
                return func(*args, **kwargs)
            return 0
        
        elif isinstance(expr, ExprCompare):
            # Handle comparisons (e.g., a == b, a < b)
            left = self.evaluate_expr(expr.left)
            # Comparisons can chain (a < b < c), but typically just one
            for op, comparator in zip(expr.ops, expr.comparators):
                right = self.evaluate_expr(comparator)
                if not self.apply_compareop(op, left, right):
                    return False
                left = right  # For chained comparisons
            return True
        
        elif isinstance(expr, ExprBool):
            # Handle boolean operations (and, or)
            if expr.op == BoolOp.And:
                # Short-circuit evaluation for 'and'
                for value in expr.values:
                    result = self.evaluate_expr(value)
                    if not result:
                        return False
                return True
            elif expr.op == BoolOp.Or:
                # Short-circuit evaluation for 'or'
                for value in expr.values:
                    result = self.evaluate_expr(value)
                    if result:
                        return True
                return False
        
        elif isinstance(expr, ExprIfExp):
            # Handle ternary conditional (a if test else b)
            test = self.evaluate_expr(expr.test)
            if test:
                return self.evaluate_expr(expr.body)
            else:
                return self.evaluate_expr(expr.orelse)
        
        elif isinstance(expr, ExprSubscript):
            # Handle subscript operations (e.g., array[index])
            base = self.evaluate_expr(expr.value)
            index = self.evaluate_expr(expr.slice)
            return base[int(index)]
        
        # Handle phase2 expressions
        from ..ir.expr_phase2 import ExprList
        if isinstance(expr, ExprList):
            # Evaluate list literal
            return [self.evaluate_expr(elt) for elt in expr.elts]
        
        else:
            raise NotImplementedError(f"Expression type {type(expr)} not implemented")
    
    def get_field_path(self, expr: Expr) -> str:
        """Get the field path string from an expression.
        
        For ExprRefField, we build the path from the field index.
        For simple components, field index maps directly to field name.
        """
        if isinstance(expr, ExprRefField):
            # Get field name from component's user fields by index (excluding _impl)
            # This must match the logic in data_model_factory._extract_fields
            fields = [f for f in dc.fields(self.component) if f.name != '_impl']
            if expr.index < len(fields):
                field = fields[expr.index]
                return field.name
            raise ValueError(f"Field index {expr.index} out of range")
        
        elif isinstance(expr, ExprAttribute):
            # Handle self.field_name
            if isinstance(expr.value, TypeExprRefSelf):
                return expr.attr
            # For nested access, we'd need to build the path recursively
            base_path = self.get_field_path(expr.value)
            return f"{base_path}.{expr.attr}"
        
        raise ValueError(f"Cannot get field path from {type(expr)}")
    
    def apply_binop(self, op: BinOp, left: Any, right: Any) -> Any:
        """Apply a binary operation."""
        if op == BinOp.Add:
            return left + right
        elif op == BinOp.Sub:
            return left - right
        elif op == BinOp.Mult:
            return left * right
        elif op == BinOp.Div:
            return left // right  # Integer division
        elif op == BinOp.Mod:
            return left % right
        elif op == BinOp.BitAnd:
            return left & right
        elif op == BinOp.BitOr:
            return left | right
        elif op == BinOp.BitXor:
            return left ^ right
        elif op == BinOp.LShift:
            return left << right
        elif op == BinOp.RShift:
            return left >> right
        elif op == BinOp.Eq:
            return left == right
        elif op == BinOp.NotEq:
            return left != right
        elif op == BinOp.Lt:
            return left < right
        elif op == BinOp.LtE:
            return left <= right
        elif op == BinOp.Gt:
            return left > right
        elif op == BinOp.GtE:
            return left >= right
        elif op == BinOp.And:
            return left and right
        elif op == BinOp.Or:
            return left or right
        else:
            raise NotImplementedError(f"Binary operation {op} not implemented")
    
    def apply_compareop(self, op: CmpOp, left: Any, right: Any) -> bool:
        """Apply a comparison operation."""
        if op == CmpOp.Eq:
            return left == right
        elif op == CmpOp.NotEq:
            return left != right
        elif op == CmpOp.Lt:
            return left < right
        elif op == CmpOp.LtE:
            return left <= right
        elif op == CmpOp.Gt:
            return left > right
        elif op == CmpOp.GtE:
            return left >= right
        elif op == CmpOp.In:
            return left in right
        elif op == CmpOp.NotIn:
            return left not in right
        elif op == CmpOp.Is:
            return left is right
        elif op == CmpOp.IsNot:
            return left is not right
        else:
            raise NotImplementedError(f"Comparison operation {op} not implemented")


class SyncProcessExecutor(Executor):
    """Executor for synchronous processes with deferred assignments."""
    
    def __init__(self, eval_state: EvalState, component: Component):
        super().__init__(eval_state, component)
        self.is_deferred = True  # Sync processes use deferred writes


class CombProcessExecutor(Executor):
    """Executor for combinational processes with immediate assignments."""
    
    def __init__(self, eval_state: EvalState, component: Component):
        super().__init__(eval_state, component)
        self.is_deferred = False  # Comb processes use immediate writes
