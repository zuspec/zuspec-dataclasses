"""Concrete constraint classes for representing parsed constraints"""

from typing import Set, Dict, Optional, List
from zuspec.dataclasses.ir.expr import BinOp, UnaryOp, BoolOp, CmpOp
from .constraint import Constraint
from .variable import Variable


class ConstantConstraint(Constraint):
    """Represents a constant value constraint"""
    
    def __init__(
        self,
        value: int,
        variables: Optional[Set[Variable]] = None,
        **kwargs
    ):
        super().__init__(variables or set(), **kwargs)
        self.value = value
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        # Constant is always satisfied (it's just a value)
        return True
    
    def __repr__(self) -> str:
        return f"Constant({self.value})"


class VariableRefConstraint(Constraint):
    """Represents a reference to a variable"""
    
    def __init__(
        self,
        variable: Variable,
        **kwargs
    ):
        super().__init__({variable}, **kwargs)
        self.variable = variable
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        # Variable reference is satisfied if variable is assigned
        return self.variable.name in assignment
    
    def __repr__(self) -> str:
        return f"VarRef({self.variable.name})"


class BinaryOpConstraint(Constraint):
    """Represents a binary operation constraint"""
    
    def __init__(
        self,
        op: BinOp,
        left: Constraint,
        right: Constraint,
        **kwargs
    ):
        # Collect variables from both operands
        variables = left.variables | right.variables
        super().__init__(variables, **kwargs)
        self.op = op
        self.left = left
        self.right = right
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        # Check if this is actually a constraint (has comparison)
        # For now, binary ops are satisfied if they can be evaluated
        if not self.left.is_satisfied(assignment) or not self.right.is_satisfied(assignment):
            return False
        return True
    
    def __repr__(self) -> str:
        return f"BinOp({self.left} {self.op.name} {self.right})"


class UnaryOpConstraint(Constraint):
    """Represents a unary operation constraint"""
    
    def __init__(
        self,
        op: UnaryOp,
        operand: Constraint,
        **kwargs
    ):
        super().__init__(operand.variables, **kwargs)
        self.op = op
        self.operand = operand
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        return self.operand.is_satisfied(assignment)
    
    def __repr__(self) -> str:
        return f"UnaryOp({self.op.name} {self.operand})"


class BoolOpConstraint(Constraint):
    """Represents a boolean operation constraint (AND, OR)"""
    
    def __init__(
        self,
        op: BoolOp,
        values: List[Constraint],
        **kwargs
    ):
        # Collect variables from all operands
        variables = set()
        for val in values:
            variables |= val.variables
        super().__init__(variables, **kwargs)
        self.op = op
        self.values = values
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if self.op == BoolOp.And:
            return all(v.is_satisfied(assignment) for v in self.values)
        elif self.op == BoolOp.Or:
            return any(v.is_satisfied(assignment) for v in self.values)
        return False
    
    def __repr__(self) -> str:
        values_str = f" {self.op.name} ".join(str(v) for v in self.values)
        return f"BoolOp({values_str})"


class CompareConstraint(Constraint):
    """Represents a comparison constraint (relational operators)"""
    
    def __init__(
        self,
        left: Constraint,
        op: CmpOp,
        right: Constraint,
        **kwargs
    ):
        # Collect variables from both operands
        variables = left.variables | right.variables
        super().__init__(variables, **kwargs)
        self.left = left
        self.op = op
        self.right = right
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        # This is a relational constraint that must be checked
        # For now, just ensure operands can be evaluated
        if not self.left.is_satisfied(assignment) or not self.right.is_satisfied(assignment):
            return False
        
        # Need to evaluate the actual comparison
        # This will be implemented when we add the evaluator
        return True
    
    def __repr__(self) -> str:
        return f"Compare({self.left} {self.op.name} {self.right})"


class CompareChainConstraint(Constraint):
    """Represents a chain of comparisons (e.g., a < b < c)"""
    
    def __init__(
        self,
        left: Constraint,
        ops: List[CmpOp],
        comparators: List[Constraint],
        **kwargs
    ):
        # Collect variables from all operands
        variables = left.variables.copy()
        for comp in comparators:
            variables |= comp.variables
        super().__init__(variables, **kwargs)
        self.left = left
        self.ops = ops
        self.comparators = comparators
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        # Check if all operands can be evaluated
        if not self.left.is_satisfied(assignment):
            return False
        for comp in self.comparators:
            if not comp.is_satisfied(assignment):
                return False
        return True
    
    def __repr__(self) -> str:
        result = str(self.left)
        for op, comp in zip(self.ops, self.comparators):
            result += f" {op.name} {comp}"
        return f"CompareChain({result})"


class InConstraint(Constraint):
    """Represents an 'in' constraint (membership test)"""
    
    def __init__(
        self,
        variable: Variable,
        values: Set[int],
        **kwargs
    ):
        super().__init__({variable}, **kwargs)
        self.variable = variable
        self.values = values
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if self.variable.name not in assignment:
            return False
        return assignment[self.variable.name] in self.values
    
    def __repr__(self) -> str:
        return f"In({self.variable.name} in {self.values})"


class BitSliceConstraint(Constraint):
    """Represents a bit-slice constraint (e.g., addr[7:0])"""
    
    def __init__(
        self,
        variable: Variable,
        lower: int,
        upper: int,
        **kwargs
    ):
        super().__init__({variable}, **kwargs)
        self.variable = variable
        self.lower = lower
        self.upper = upper
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        # Bit slice is satisfied if the variable is assigned
        return self.variable.name in assignment
    
    def __repr__(self) -> str:
        return f"BitSlice({self.variable.name}[{self.upper}:{self.lower}])"


class ImplicationConstraint(Constraint):
    """Represents an implication constraint (if-then-else)"""
    
    def __init__(
        self,
        condition: Constraint,
        then_constraint: Constraint,
        else_constraint: Optional[Constraint] = None,
        **kwargs
    ):
        variables = condition.variables | then_constraint.variables
        if else_constraint:
            variables |= else_constraint.variables
        super().__init__(variables, **kwargs)
        self.condition = condition
        self.then_constraint = then_constraint
        self.else_constraint = else_constraint
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        # All parts must be evaluatable
        if not self.condition.is_satisfied(assignment):
            return False
        if not self.then_constraint.is_satisfied(assignment):
            return False
        if self.else_constraint and not self.else_constraint.is_satisfied(assignment):
            return False
        return True
    
    def __repr__(self) -> str:
        result = f"Implication({self.condition} -> {self.then_constraint}"
        if self.else_constraint:
            result += f" : {self.else_constraint}"
        result += ")"
        return result
