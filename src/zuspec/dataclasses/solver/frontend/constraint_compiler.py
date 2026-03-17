"""Compile constraint AST into propagators for the solver engine"""

from typing import Dict, List, Optional, Tuple
from zuspec.dataclasses.ir.expr import BinOp, UnaryOp, BoolOp, CmpOp

from ..core.constraint import Constraint
from ..core.constraints import (
    ConstantConstraint, VariableRefConstraint, BinaryOpConstraint,
    UnaryOpConstraint, BoolOpConstraint, CompareConstraint,
    CompareChainConstraint, ImplicationConstraint, InConstraint, UniqueConstraint
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
    ModPropagator, DivPropagator, EqualSumPropagator
)
from ..propagators.implication import ImplicationPropagator, BoolNotPropagator, BoolOrPropagator
from ..propagators.reification import ComparisonReifier
from ..propagators.reification import DisjunctiveComparisonPropagator
from ..propagators.uniqueness import UniquePropagator, PairwiseUniquePropagator


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

        elif isinstance(constraint, InConstraint):
            return self._compile_in(constraint)

        elif isinstance(constraint, UniqueConstraint):
            return self._compile_unique(constraint)

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
        # Fast path: X == Y + Z  ->  fused EqualSumPropagator (no temp var)
        if not reify and constraint.op == CmpOp.Eq:
            if isinstance(constraint.right, BinaryOpConstraint) and constraint.right.op == BinOp.Add:
                lhs_var = self._compile_constraint(constraint.left)
                a_var = self._compile_constraint(constraint.right.left)
                b_var = self._compile_constraint(constraint.right.right)
                if all(v is not None for v in (lhs_var, a_var, b_var)):
                    self.propagators.append(EqualSumPropagator(lhs_var, a_var, b_var))
                    return None
            if isinstance(constraint.left, BinaryOpConstraint) and constraint.left.op == BinOp.Add:
                rhs_var = self._compile_constraint(constraint.right)
                a_var = self._compile_constraint(constraint.left.left)
                b_var = self._compile_constraint(constraint.left.right)
                if all(v is not None for v in (rhs_var, a_var, b_var)):
                    self.propagators.append(EqualSumPropagator(rhs_var, a_var, b_var))
                    return None

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
        For OR: use direct disjunctive propagator when both operands are
        simple comparisons; otherwise fall back to reification + BoolOrPropagator.
        """
        if constraint.op == BoolOp.And:
            # AND: compile each sub-constraint independently
            for value in constraint.values:
                self._compile_constraint(value)
            return None
        elif constraint.op == BoolOp.Or:
            # Fast path: N-operand Or where every operand is a simple comparison
            if len(constraint.values) >= 2 and all(
                isinstance(v, CompareConstraint) for v in constraint.values
            ):
                try:
                    clauses = []
                    for v in constraint.values:
                        lv = self._compile_constraint(v.left)
                        rv = self._compile_constraint(v.right)
                        if lv is None or rv is None:
                            raise CompilationError("operand produced no value")
                        clauses.append((lv, v.op, rv))
                    self.propagators.append(
                        DisjunctiveComparisonPropagator(clauses))
                    return None
                except CompilationError:
                    pass  # fall through to reification

            # OR: reify each operand, then enforce "at least one is true"
            bool_vars = []
            for value in constraint.values:
                bool_var = self._compile_constraint(value, reify=True)
                if bool_var is None:
                    raise CompilationError("OR operand cannot be reified")
                bool_vars.append(bool_var)
            self.propagators.append(BoolOrPropagator(bool_vars))
            return None
        else:
            raise CompilationError(f"Unsupported boolean operator: {constraint.op}")
    
    def _compile_unary_op(self, constraint: UnaryOpConstraint) -> Optional[str]:
        """
        Compile a unary NOT constraint.

        For NOT of a comparison, flip the comparison operator.
        For NOT of a boolean op, apply De Morgan's law recursively.
        """
        if constraint.op != UnaryOp.Not:
            raise CompilationError(f"Unsupported unary operator: {constraint.op}")

        inner = constraint.operand

        if isinstance(inner, CompareConstraint):
            # Flip the comparison operator: !(a op b) → (a negated_op b)
            negated_op = {
                CmpOp.Eq:  CmpOp.NotEq,
                CmpOp.NotEq: CmpOp.Eq,
                CmpOp.Lt:  CmpOp.GtE,
                CmpOp.LtE: CmpOp.Gt,
                CmpOp.Gt:  CmpOp.LtE,
                CmpOp.GtE: CmpOp.Lt,
            }.get(inner.op)
            if negated_op is None:
                raise CompilationError(f"Cannot negate comparison operator: {inner.op}")
            from ..core.constraints import CompareConstraint as CC
            negated = CC(left=inner.left, op=negated_op, right=inner.right,
                         source_location=inner.source_location)
            return self._compile_compare(negated, reify=False)

        elif isinstance(inner, BoolOpConstraint):
            # De Morgan: !(A && B) = !A || !B;  !(A || B) = !A && !B
            from ..core.constraints import UnaryOpConstraint as UOC
            negated_values = [
                UOC(op=UnaryOp.Not, operand=v, source_location=inner.source_location)
                for v in inner.values
            ]
            flipped_op = BoolOp.Or if inner.op == BoolOp.And else BoolOp.And
            negated_bool = BoolOpConstraint(
                op=flipped_op,
                values=negated_values,
                source_location=inner.source_location,
            )
            return self._compile_bool_op(negated_bool)

        else:
            raise CompilationError(
                f"NOT of {type(inner).__name__} is not supported"
            )
    
    def _compile_implication(self, constraint: ImplicationConstraint) -> Optional[str]:
        """
        Compile an implication constraint (if-else).

        For: if condition -> then_constraint [else else_constraint]

        Compiled as:
          condition_var  -> then_var   (condition → then)
          !condition_var -> else_var   (else branch, if present)
        """
        condition_var = self._compile_constraint(constraint.condition, reify=True)
        then_var = self._compile_constraint(constraint.then_constraint, reify=True)

        if condition_var is None or then_var is None:
            raise CompilationError("Implication operands must produce boolean values")

        self.propagators.append(ImplicationPropagator(condition_var, then_var))

        if constraint.else_constraint is not None:
            else_var = self._compile_constraint(constraint.else_constraint, reify=True)
            if else_var is None:
                raise CompilationError("Else constraint must produce a boolean value")

            neg_cond_var = self._create_bool_var()
            self.propagators.append(BoolNotPropagator(condition_var, neg_cond_var))
            self.propagators.append(ImplicationPropagator(neg_cond_var, else_var))

        return None

    def _compile_in(self, constraint: InConstraint) -> None:
        """
        Compile an 'in' constraint by restricting the variable's domain.

        Intersects the variable's current domain with the valid value set.
        If the intersection is empty, raises CompilationError.
        """
        var = constraint.variable
        valid = constraint.values

        # Build an IntDomain from the valid values (each value as a singleton interval)
        intervals = [(v, v) for v in sorted(valid)]
        new_domain = IntDomain(intervals, var.domain.width, var.domain.signed)

        restricted = var.domain.intersect(new_domain)
        if restricted.is_empty():
            raise CompilationError(
                f"'in' constraint for '{var.name}' results in an empty domain"
            )
        var.domain = restricted
        return None

    def _compile_unique(self, constraint: UniqueConstraint) -> None:
        """
        Compile a unique constraint by adding a UniquePropagator or PairwiseUniquePropagator.
        """
        var_names = [v.name for v in constraint.unique_variables]
        if len(var_names) == 2:
            self.propagators.append(PairwiseUniquePropagator(var_names[0], var_names[1]))
        else:
            self.propagators.append(UniquePropagator(var_names))
        return None


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
