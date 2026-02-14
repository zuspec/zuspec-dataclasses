"""Compile constraint AST into propagators for the solver engine"""

from typing import Dict, List, Optional, Tuple
from zuspec.dataclasses.ir.expr import BinOp, UnaryOp, BoolOp, CmpOp

from ..core.constraint import Constraint
from ..core.constraints import (
    ConstantConstraint, VariableRefConstraint, BinaryOpConstraint,
    UnaryOpConstraint, BoolOpConstraint, CompareConstraint,
    CompareChainConstraint, ImplicationConstraint
)
from ..core.variable import Variable
from ..core.domain import IntDomain
from ..propagators.base import Propagator
from ..propagators.relational import (
    EqualPropagator, NotEqualPropagator, LessThanPropagator,
    LessEqualPropagator, GreaterThanPropagator,
    GreaterEqualPropagator
)
from ..propagators.arithmetic import (
    AddPropagator, SubPropagator, MultPropagator,
    ModPropagator, DivPropagator
)
from ..propagators.implication import ImplicationPropagator
from ..propagators.reification import ComparisonReifier


class CompilationError(Exception):
    """Raised when constraint compilation fails"""
    pass


class ConstraintCompiler:
    """
    Compiles constraint AST into propagators.
    
    Converts high-level Constraint objects (from IR parsing) into
    low-level Propagator objects that can be executed by the engine.
    """
    
    def __init__(self, variables: Dict[str, Variable]):
        """
        Initialize compiler.
        
        Args:
            variables: Map from variable names to Variable objects
        """
        self.variables = variables
        self.temp_var_counter = 0
        self.propagators: List[Propagator] = []
        
    def compile(self, constraint: Constraint) -> List[Propagator]:
        """
        Compile a constraint into zero or more propagators.
        
        Args:
            constraint: Constraint to compile
            
        Returns:
            List of propagators that enforce the constraint
            
        Raises:
            CompilationError: If constraint cannot be compiled
        """
        self.propagators = []
        self._compile_constraint(constraint)
        return self.propagators
    
    def _compile_constraint(self, constraint: Constraint, reify: bool = False) -> Optional[str]:
        """
        Recursively compile a constraint.
        
        Args:
            constraint: Constraint to compile
            reify: If True, create a boolean result variable (for implications)
        
        Returns:
            Variable name holding the result, or None for top-level constraints
        """
        if isinstance(constraint, CompareConstraint):
            return self._compile_compare(constraint, reify=reify)
            
        elif isinstance(constraint, BinaryOpConstraint):
            return self._compile_binary_op(constraint)
            
        elif isinstance(constraint, VariableRefConstraint):
            return constraint.variable.name
            
        elif isinstance(constraint, ConstantConstraint):
            # Create a temporary variable to hold the constant
            return self._create_constant_var(constraint.value)
            
        elif isinstance(constraint, BoolOpConstraint):
            return self._compile_bool_op(constraint)
            
        elif isinstance(constraint, UnaryOpConstraint):
            return self._compile_unary_op(constraint)
            
        elif isinstance(constraint, ImplicationConstraint):
            return self._compile_implication(constraint)
            
        else:
            raise CompilationError(
                f"Unsupported constraint type: {constraint.__class__.__name__}"
            )
    
    def _compile_compare(self, constraint: CompareConstraint, reify: bool = False) -> Optional[str]:
        """
        Compile a comparison constraint.
        
        Args:
            constraint: Comparison constraint to compile
            reify: If True, create a boolean result variable instead of direct propagator
        
        Returns:
            If reify=True: name of boolean variable (0/1)
            If reify=False: None (creates propagator directly)
        """
        # Compile operands
        left_var = self._compile_constraint(constraint.left)
        right_var = self._compile_constraint(constraint.right)
        
        if left_var is None or right_var is None:
            raise CompilationError("Comparison operands must produce values")
        
        if reify:
            # Reification mode: create boolean result variable
            bool_var = self._create_bool_var()
            
            # Create reifier propagator
            reifier = ComparisonReifier(bool_var, left_var, constraint.op, right_var)
            self.propagators.append(reifier)
            
            return bool_var
        else:
            # Direct mode: create comparison propagator without result variable
            # Create appropriate propagator based on operator
            if constraint.op == CmpOp.Eq:
                prop = EqualPropagator(left_var, right_var)
            elif constraint.op == CmpOp.NotEq:
                prop = NotEqualPropagator(left_var, right_var)
            elif constraint.op == CmpOp.Lt:
                prop = LessThanPropagator(left_var, right_var)
            elif constraint.op == CmpOp.LtE:
                prop = LessEqualPropagator(left_var, right_var)
            elif constraint.op == CmpOp.Gt:
                prop = GreaterThanPropagator(left_var, right_var)
            elif constraint.op == CmpOp.GtE:
                prop = GreaterEqualPropagator(left_var, right_var)
            else:
                raise CompilationError(f"Unsupported comparison operator: {constraint.op}")
            
            self.propagators.append(prop)
            return None  # Top-level constraint, no result variable
    
    def _compile_binary_op(self, constraint: BinaryOpConstraint) -> str:
        """
        Compile a binary operation constraint.
        
        Creates a temporary variable and propagator for the operation.
        """
        # Compile operands
        left_var = self._compile_constraint(constraint.left)
        right_var = self._compile_constraint(constraint.right)
        
        if left_var is None or right_var is None:
            raise CompilationError("Binary operation operands must produce values")
        
        # Create result variable
        result_var = self._create_temp_var()
        
        # Create appropriate propagator based on operator
        if constraint.op == BinOp.Add:
            prop = AddPropagator(result_var, left_var, right_var)
        elif constraint.op == BinOp.Sub:
            prop = SubPropagator(result_var, left_var, right_var)
        elif constraint.op == BinOp.Mult:
            prop = MultPropagator(result_var, left_var, right_var)
        elif constraint.op == BinOp.Mod:
            prop = ModPropagator(result_var, left_var, right_var)
        elif constraint.op == BinOp.Div:
            prop = DivPropagator(result_var, left_var, right_var)
        else:
            raise CompilationError(f"Unsupported binary operator: {constraint.op}")
        
        self.propagators.append(prop)
        return result_var
    
    def _compile_bool_op(self, constraint: BoolOpConstraint) -> Optional[str]:
        """
        Compile a boolean operation (AND/OR).
        
        For AND: all sub-constraints must be satisfied (just compile each)
        For OR: requires disjunction support (not yet implemented)
        """
        if constraint.op == BoolOp.And:
            # AND: compile each sub-constraint independently
            for value in constraint.values:
                self._compile_constraint(value)
            return None
        elif constraint.op == BoolOp.Or:
            # OR: requires disjunction support
            raise CompilationError("OR operator not yet implemented")
        else:
            raise CompilationError(f"Unsupported boolean operator: {constraint.op}")
    
    def _compile_unary_op(self, constraint: UnaryOpConstraint) -> str:
        """
        Compile a unary operation.
        
        Currently only NOT is common, but propagation is complex.
        """
        raise CompilationError("Unary operators not yet implemented")
    
    def _compile_implication(self, constraint: ImplicationConstraint) -> Optional[str]:
        """
        Compile an implication constraint.
        
        For: condition -> then_constraint
        
        The ImplicationPropagator works with boolean variables (0 or 1).
        We need to:
        1. Compile condition to a boolean variable (reify=True)
        2. Compile then_constraint to a boolean variable (reify=True)
        3. Create ImplicationPropagator between them
        """
        # Compile condition with reification to get a boolean variable
        condition_var = self._compile_constraint(constraint.condition, reify=True)
        
        # Compile then_constraint with reification to get a boolean variable
        then_var = self._compile_constraint(constraint.then_constraint, reify=True)
        
        if condition_var is None or then_var is None:
            raise CompilationError("Implication operands must produce boolean values")
        
        # Create the implication propagator
        prop = ImplicationPropagator(condition_var, then_var)
        self.propagators.append(prop)
        
        return None  # Top-level constraint, no result variable
    
    def _create_temp_var(self) -> str:
        """Create a temporary variable for intermediate results"""
        name = f"_temp_{self.temp_var_counter}"
        self.temp_var_counter += 1
        
        # Create variable with full integer range
        # Width should be determined by operation, but for now use 64-bit
        temp_var = Variable(
            name=name,
            domain=IntDomain([(-(2**63), 2**63 - 1)], width=64, signed=True)
        )
        self.variables[name] = temp_var
        
        return name
    
    def _create_bool_var(self) -> str:
        """Create a boolean variable (domain {0, 1}) for reification"""
        name = f"_bool_{self.temp_var_counter}"
        self.temp_var_counter += 1
        
        # Create variable with boolean domain {0, 1}
        bool_var = Variable(
            name=name,
            domain=IntDomain([(0, 1)], width=1, signed=False)
        )
        self.variables[name] = bool_var
        
        return name
    
    def _create_constant_var(self, value: int) -> str:
        """Create a variable with a single constant value"""
        name = f"_const_{value}_{self.temp_var_counter}"
        self.temp_var_counter += 1
        
        # Create variable with singleton domain
        const_var = Variable(
            name=name,
            domain=IntDomain([(value, value)], width=64, signed=True)
        )
        self.variables[name] = const_var
        
        return name
