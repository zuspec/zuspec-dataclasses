"""Compile constraint AST into propagators for the solver engine"""

from typing import Dict, List, Optional, Tuple
from zuspec.ir.core.expr import BinOp, UnaryOp, BoolOp, CmpOp

from ..core.constraint import Constraint
from ..core.constraints import (
    ConstantConstraint, VariableRefConstraint, BinaryOpConstraint,
    UnaryOpConstraint, BoolOpConstraint, CompareConstraint,
    CompareChainConstraint, ImplicationConstraint, InConstraint, UniqueConstraint,
    SextConstraint, CbitConstraint, SignedViewConstraint,
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
from ..propagators.implication import ImplicationPropagator, BoolNotPropagator, BoolOrPropagator, BoolAndPropagator
from ..propagators.reification import ComparisonReifier
from ..propagators.reification import DisjunctiveComparisonPropagator
from ..propagators.bitwise import (
    BitAndPropagator, BitOrPropagator, BitXorPropagator,
    LShiftPropagator, RShiftPropagator, FloorDivPropagator,
    BitInvertPropagator,
)
from ..propagators.uniqueness import UniquePropagator, PairwiseUniquePropagator
from ..propagators.functions import SextPropagator, CbitPropagator, SignedViewPropagator


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
        # Cache: (value, width, signed) → variable name
        # Avoids creating duplicate constant variables for the same value,
        # dramatically reducing variable count for constant-folded systems.
        self._const_cache: Dict[tuple, str] = {}
        
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
            return self._compile_bool_op(constraint, reify=reify)
            
        elif isinstance(constraint, UnaryOpConstraint):
            return self._compile_unary_op(constraint, reify=reify)
            
        elif isinstance(constraint, ImplicationConstraint):
            return self._compile_implication(constraint)

        elif isinstance(constraint, InConstraint):
            return self._compile_in(constraint)

        elif isinstance(constraint, UniqueConstraint):
            return self._compile_unique(constraint)

        elif isinstance(constraint, SextConstraint):
            return self._compile_sext(constraint)

        elif isinstance(constraint, CbitConstraint):
            return self._compile_cbit(constraint)

        elif isinstance(constraint, SignedViewConstraint):
            return self._compile_signed_view(constraint)

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
            # Constant-fold: if both sides are already singletons, return a
            # constant bool var without emitting a propagator.
            lv = self.variables.get(left_var)
            rv = self.variables.get(right_var)
            if lv is not None and rv is not None and lv.domain.is_singleton() and rv.domain.is_singleton():
                lval, rval = lv.domain.min_val, rv.domain.min_val
                op = constraint.op
                truth = (
                    (op == CmpOp.Eq    and lval == rval) or
                    (op == CmpOp.NotEq and lval != rval) or
                    (op == CmpOp.Lt    and lval <  rval) or
                    (op == CmpOp.LtE   and lval <= rval) or
                    (op == CmpOp.Gt    and lval >  rval) or
                    (op == CmpOp.GtE   and lval >= rval)
                )
                return self._create_bool_constant_var(1 if truth else 0)
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
    
    def _compile_operand(self, constraint: 'Constraint') -> Optional[str]:
        """Compile a constraint as a value-producing operand.

        Comparisons and boolean ops are automatically reified to 0/1 variables
        when used as operands so they can participate in arithmetic/bitwise operations.
        """
        if isinstance(constraint, CompareConstraint):
            return self._compile_compare(constraint, reify=True)
        if isinstance(constraint, BoolOpConstraint):
            return self._compile_bool_op(constraint, reify=True)
        return self._compile_constraint(constraint)

    def _compile_binary_op(self, constraint: BinaryOpConstraint) -> str:
        """
        Compile a binary operation constraint.

        Creates a temporary variable and propagator for the operation.
        If both operands reduce to singleton (constant) variables the result
        is constant-folded into a single constant variable without any propagator.
        """
        # Compile operands — comparisons used as values are automatically reified
        left_var = self._compile_operand(constraint.left)
        right_var = self._compile_operand(constraint.right)

        if left_var is None or right_var is None:
            raise CompilationError("Binary operation operands must produce values")

        # Constant-fold: if both variables are already singletons, compute
        # the result at compile time and return a constant var.
        lv = self.variables.get(left_var)
        rv = self.variables.get(right_var)
        if lv is not None and rv is not None and lv.domain.is_singleton() and rv.domain.is_singleton():
            lval = lv.domain.min_val
            rval = rv.domain.min_val
            op = constraint.op
            if   op == BinOp.Add:      result = lval + rval
            elif op == BinOp.Sub:      result = lval - rval
            elif op == BinOp.Mult:     result = lval * rval
            elif op == BinOp.Mod:      result = lval % rval if rval else 0
            elif op == BinOp.Div:      result = int(lval / rval) if rval else 0
            elif op == BinOp.FloorDiv: result = lval // rval if rval else 0
            elif op in (BinOp.BitAnd, BinOp.BitOr, BinOp.BitXor):
                # Sign-extend 1-bit booleans before bitwise ops: RTL semantics where
                # a 1-bit comparison signal is all-ones (true) or all-zeros (false).
                leff = (-1 if lval else 0) if lv.domain.width == 1 else lval
                reff = (-1 if rval else 0) if rv.domain.width == 1 else rval
                if   op == BinOp.BitAnd: result = leff & reff
                elif op == BinOp.BitOr:  result = leff | reff
                else:                    result = leff ^ reff
            elif op == BinOp.LShift:   result = lval << rval
            elif op == BinOp.RShift:   result = lval >> rval
            else: result = None
            if result is not None:
                return self._create_constant_var(result)

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
        elif constraint.op == BinOp.FloorDiv:
            prop = FloorDivPropagator(result_var, left_var, right_var)
        elif constraint.op == BinOp.BitAnd:
            left_var = self._extend_bool(left_var)
            right_var = self._extend_bool(right_var)
            prop = BitAndPropagator(result_var, left_var, right_var)
        elif constraint.op == BinOp.BitOr:
            left_var = self._extend_bool(left_var)
            right_var = self._extend_bool(right_var)
            prop = BitOrPropagator(result_var, left_var, right_var)
        elif constraint.op == BinOp.BitXor:
            left_var = self._extend_bool(left_var)
            right_var = self._extend_bool(right_var)
            prop = BitXorPropagator(result_var, left_var, right_var)
        elif constraint.op == BinOp.LShift:
            prop = LShiftPropagator(result_var, left_var, right_var)
        elif constraint.op == BinOp.RShift:
            prop = RShiftPropagator(result_var, left_var, right_var)
        else:
            raise CompilationError(f"Unsupported binary operator: {constraint.op}")
        
        self.propagators.append(prop)
        return result_var
    
    def _compile_bool_op(self, constraint: BoolOpConstraint, reify: bool = False) -> Optional[str]:
        """
        Compile a boolean operation (AND/OR).
        
        For AND (non-reify): all sub-constraints must be satisfied (just compile each)
        For AND (reify): reify each operand, combine with BoolAndPropagator
        For OR: use direct disjunctive propagator when both operands are
        simple comparisons; otherwise fall back to reification + BoolOrPropagator.
        """
        if constraint.op == BoolOp.And:
            if reify:
                # Reify the AND: result_var = 1 iff all operands are 1
                bool_vars = []
                for value in constraint.values:
                    bv = self._compile_constraint(value, reify=True)
                    if bv is None:
                        raise CompilationError("AND operand cannot be reified")
                    bool_vars.append(bv)
                result_var = self._create_bool_var()
                self.propagators.append(BoolAndPropagator(result_var, bool_vars))
                return result_var
            else:
                # AND: compile each sub-constraint independently
                for value in constraint.values:
                    self._compile_constraint(value)
                return None
        elif constraint.op == BoolOp.Or:
            # Fast path: N-operand Or where every operand is a simple comparison.
            # Only applicable when not reifying (DisjunctiveComparisonPropagator has no result var).
            if not reify and len(constraint.values) >= 2 and all(
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
            if reify:
                result_var = self._create_bool_var()
                self.propagators.append(BoolOrPropagator(bool_vars, result_var=result_var))
                return result_var
            self.propagators.append(BoolOrPropagator(bool_vars))
            return None
        else:
            raise CompilationError(f"Unsupported boolean operator: {constraint.op}")
    
    def _compile_unary_op(self, constraint: UnaryOpConstraint, reify: bool = False) -> Optional[str]:
        """
        Compile a unary operation constraint.

        Handles NOT (logical/comparison negation) and Invert (bitwise ~).
        When *reify* is True, the result must be a named bool variable (0/1).
        """
        if constraint.op == UnaryOp.Invert:
            # Bitwise NOT: result = ~operand  (Python: ~x == -(x+1))
            operand_var = self._compile_operand(constraint.operand)
            if operand_var is None:
                raise CompilationError("Invert operand must produce a value")
            # Sign-extend 1-bit booleans before inverting:
            # ~(sext(1)) = ~(-1) = 0,  ~(sext(0)) = ~(0) = -1 — correct RTL NOT
            operand_var = self._extend_bool(operand_var)
            ov = self.variables.get(operand_var)
            if ov is not None and ov.domain.is_singleton():
                return self._create_constant_var(~ov.domain.min_val)
            result_var = self._create_temp_var()
            self.propagators.append(BitInvertPropagator(result_var, operand_var))
            return result_var

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
            return self._compile_compare(negated, reify=reify)

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
            return self._compile_bool_op(negated_bool, reify=reify)

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

        Compound AND conditions are handled by _compile_bool_op(reify=True) which
        produces a BoolAndPropagator that reifies the AND into a single boolean var.
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
        # Look up the variable by name in the compiler's own variables dict so that
        # domain narrowing applies to the *copy* being solved, not the shared template.
        var = self.variables.get(constraint.variable.name, constraint.variable)
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
        """Create (or reuse) a variable with a single constant value.

        Cached by (value, width=64, signed=True) so that duplicate constants
        within the same compilation share a single Variable object rather than
        creating hundreds of identical singleton variables.
        """
        key = (value, 64, True)
        cached = self._const_cache.get(key)
        if cached is not None:
            return cached
        name = f"_const_{value}_{self.temp_var_counter}"
        self.temp_var_counter += 1
        const_var = Variable(
            name=name,
            domain=IntDomain([(value, value)], width=64, signed=True)
        )
        self.variables[name] = const_var
        self._const_cache[key] = name
        return name

    def _create_bool_constant_var(self, value: int) -> str:
        """Create (or reuse) a width=1 boolean constant variable (0 or 1).

        Width=1 signals that this value is a boolean selector that should be
        sign-extended (0 → 0, 1 → -1) when used in bitwise-AND or bitwise-NOT
        contexts, matching RTL semantics where a 1-bit signal gates a wider bus.
        """
        key = (value, 1, False)
        cached = self._const_cache.get(key)
        if cached is not None:
            return cached
        name = f"_bconst_{value}_{self.temp_var_counter}"
        self.temp_var_counter += 1
        bool_const_var = Variable(
            name=name,
            domain=IntDomain([(value, value)], width=1, signed=False)
        )
        self.variables[name] = bool_const_var
        self._const_cache[key] = name
        return name

    def _extend_bool(self, var_name: str) -> str:
        """If var has width=1 (boolean), insert sext(var,1) so it produces 0 or -1.

        This matches RTL semantics: a 1-bit true signal gates a full-width bus.
        Width > 1 variables are returned unchanged.
        """
        var = self.variables.get(var_name)
        if var is None or var.domain.width != 1:
            return var_name
        # Singleton: fold at compile time
        if var.domain.is_singleton():
            return self._create_constant_var(-1 if var.domain.min_val else 0)
        # Non-singleton width=1: insert SextPropagator(result, var, 1)
        # SextPropagator with bits=1 maps {0→0, 1→-1}
        result_name = f"_bext_{self.temp_var_counter}"
        self.temp_var_counter += 1
        result_var_obj = Variable(
            name=result_name,
            domain=IntDomain([(-1, 0)], width=64, signed=True)
        )
        self.variables[result_name] = result_var_obj
        self.propagators.append(SextPropagator(result_name, var_name, 1))
        return result_name

    def _compile_sext(self, constraint: SextConstraint) -> str:
        """Compile sext(value, bits) into a result temp variable + SextPropagator."""
        value_name = self._compile_constraint(constraint.value)
        # bits must be a compile-time constant (ConstantConstraint or constant var)
        if isinstance(constraint.bits, ConstantConstraint):
            bits = constraint.bits.value
        else:
            bits_name = self._compile_constraint(constraint.bits)
            bits_var = self.variables.get(bits_name)
            if bits_var is None:
                raise CompilationError("sext() bits argument must be a constant")
            domain_vals = list(bits_var.domain.values())
            if len(domain_vals) != 1:
                raise CompilationError("sext() bits argument must be a compile-time constant")
            bits = domain_vals[0]

        # Constant-fold: value is already a singleton
        vv = self.variables.get(value_name)
        if vv is not None and vv.domain.is_singleton():
            raw = vv.domain.min_val
            # Two's complement sign extension
            if raw & (1 << (bits - 1)):
                raw = raw - (1 << bits)
            return self._create_constant_var(raw)

        result_name = f"_sext_{self.temp_var_counter}"
        self.temp_var_counter += 1
        result_var = Variable(
            name=result_name,
            domain=IntDomain([(-2**31, 2**31 - 1)], width=32, signed=True)
        )
        self.variables[result_name] = result_var
        self.propagators.append(SextPropagator(result_name, value_name, bits))
        return result_name

    def _compile_cbit(self, constraint: CbitConstraint) -> str:
        """Compile cbit(expr) into a result temp variable with domain {0,1}."""
        inner_name = self._compile_operand(constraint.expr)
        if inner_name is None:
            raise CompilationError(
                f"cbit() argument must produce a value, but {type(constraint.expr).__name__} "
                f"compiled to None. expr={constraint.expr!r}"
            )
        # Constant-fold: inner is already a singleton → cbit is just 0 or 1
        iv = self.variables.get(inner_name)
        if iv is not None and iv.domain.is_singleton():
            return self._create_constant_var(1 if iv.domain.min_val != 0 else 0)

        result_name = f"_cbit_{self.temp_var_counter}"
        self.temp_var_counter += 1
        result_var = Variable(
            name=result_name,
            domain=IntDomain([(0, 1)], width=64, signed=False)
        )
        self.variables[result_name] = result_var
        self.propagators.append(CbitPropagator(result_name, inner_name))
        return result_name

    def _compile_signed_view(self, constraint: SignedViewConstraint) -> str:
        """Compile signed(val) into a signed-view temp variable + SignedViewPropagator."""
        inner_name = self._compile_operand(constraint.inner)
        # Constant-fold: inner is already a singleton → reinterpret as signed two's complement
        iv = self.variables.get(inner_name)
        if iv is not None and iv.domain.is_singleton():
            raw = iv.domain.min_val
            width = constraint.width  # e.g. 32
            # Reinterpret unsigned value as signed (two's complement)
            if raw >= (1 << (width - 1)):
                raw = raw - (1 << width)
            return self._create_constant_var(raw)

        result_name = f"_signed_{self.temp_var_counter}"
        self.temp_var_counter += 1
        result_var = Variable(
            name=result_name,
            domain=IntDomain([(-2**31, 2**31 - 1)], width=32, signed=True)
        )
        self.variables[result_name] = result_var
        self.propagators.append(SignedViewPropagator(result_name, inner_name,
                                                     width=constraint.width))
        return result_name
