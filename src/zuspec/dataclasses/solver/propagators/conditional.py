"""Conditional constraint support for PSS constraint solving.

Implements if-else constraint blocks and ternary expressions.
"""

from typing import Dict, Set, List, Optional, Callable
from ..core.variable import Variable
from .base import Propagator, PropagationResult, PropagationStatus


class ConditionalConstraint(Propagator):
    """
    Conditional constraint: if (condition) then_constraints else else_constraints
    
    Semantics:
    - Evaluate condition
    - If condition is true, activate then_constraints
    - If condition is false, activate else_constraints
    - If condition is undetermined, wait
    
    Example PSS:
        if (mode == READ)
            addr < 0x100;
        else
            addr >= 0x100;
    """
    
    def __init__(
        self,
        condition_evaluator: Callable[[Dict[str, Variable]], Optional[bool]],
        condition_vars: Set[str],
        then_propagators: List[Propagator],
        else_propagators: Optional[List[Propagator]] = None
    ):
        """
        Initialize conditional constraint.
        
        Args:
            condition_evaluator: Function to evaluate condition given variables
            condition_vars: Variables involved in condition
            then_propagators: Propagators to activate if condition is true
            else_propagators: Propagators to activate if condition is false
        """
        self.condition_evaluator = condition_evaluator
        self.condition_vars = condition_vars
        self.then_propagators = then_propagators
        self.else_propagators = else_propagators or []
        
        # Track which branch is active
        self._active_branch: Optional[str] = None  # 'then', 'else', or None
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Propagate conditional constraint.
        
        Algorithm:
        1. Evaluate condition
        2. If determined, activate appropriate branch
        3. If undetermined, wait
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            PropagationResult
        """
        # Check if all condition variables are available
        if not all(var in variables for var in self.condition_vars):
            return PropagationResult.fixed_point()
        
        # Evaluate condition
        cond_result = self.condition_evaluator(variables)
        
        if cond_result is None:
            # Condition not yet determined
            return PropagationResult.fixed_point()
        
        # Activate appropriate branch
        if cond_result:
            self._active_branch = 'then'
            return self._propagate_branch(self.then_propagators, variables)
        else:
            self._active_branch = 'else'
            return self._propagate_branch(self.else_propagators, variables)
    
    def _propagate_branch(
        self,
        propagators: List[Propagator],
        variables: Dict[str, Variable]
    ) -> PropagationResult:
        """
        Propagate a specific branch.
        
        Args:
            propagators: Propagators in the branch
            variables: Variables
            
        Returns:
            Combined propagation result
        """
        if not propagators:
            return PropagationResult.fixed_point()
        
        all_changed = set()
        
        for prop in propagators:
            result = prop.propagate(variables)
            
            if result.is_conflict():
                return result
            
            all_changed.update(result.changed_vars)
        
        if all_changed:
            return PropagationResult.consistent(all_changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        """Get all variables that could be affected"""
        affected = set(self.condition_vars)
        
        for prop in self.then_propagators:
            affected.update(prop.affected_variables())
        
        for prop in self.else_propagators:
            affected.update(prop.affected_variables())
        
        return affected
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """
        Check if conditional constraint is satisfied.
        
        Args:
            assignment: Variable assignments
            
        Returns:
            True if satisfied
        """
        # Need to evaluate condition with assignment
        # This is simplified - in practice, condition_evaluator would need
        # to work with assignments instead of variables
        
        # For now, check active branch
        if self._active_branch == 'then':
            return all(p.is_satisfied(assignment) for p in self.then_propagators)
        elif self._active_branch == 'else':
            return all(p.is_satisfied(assignment) for p in self.else_propagators)
        else:
            # Condition not evaluated yet
            return False
    
    def __repr__(self) -> str:
        return f"ConditionalConstraint(then={len(self.then_propagators)}, else={len(self.else_propagators)})"


class TernaryExpressionPropagator(Propagator):
    """
    Ternary expression constraint: result = (condition ? true_val : false_val)
    
    Example PSS:
        data == (mode == READ ? 0 : write_val)
    
    This propagates the constraint based on the condition value.
    """
    
    def __init__(
        self,
        result_var: str,
        condition_var: str,
        true_val_var: str,
        false_val_var: str
    ):
        """
        Initialize ternary expression propagator.
        
        Args:
            result_var: Result variable name
            condition_var: Condition variable (boolean)
            true_val_var: Variable used if condition is true
            false_val_var: Variable used if condition is false
        """
        self.result_var = result_var
        self.condition_var = condition_var
        self.true_val_var = true_val_var
        self.false_val_var = false_val_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Propagate ternary expression.
        
        Cases:
        1. If condition = 1 (true), enforce result = true_val
        2. If condition = 0 (false), enforce result = false_val
        3. If condition undetermined, try to infer from result
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            PropagationResult
        """
        required_vars = [self.result_var, self.condition_var, 
                        self.true_val_var, self.false_val_var]
        
        if not all(v in variables for v in required_vars):
            return PropagationResult.fixed_point()
        
        result = variables[self.result_var]
        condition = variables[self.condition_var]
        true_val = variables[self.true_val_var]
        false_val = variables[self.false_val_var]
        
        changed = set()
        
        # Check if condition is determined
        if self._is_true(condition):
            # result must equal true_val
            result_domain = result.domain.intersect(true_val.domain)
            if result_domain.is_empty():
                return PropagationResult.conflict()
            
            if result_domain != result.domain:
                result.domain = result_domain
                changed.add(result)
            
            # Also constrain true_val to match result
            true_domain = true_val.domain.intersect(result.domain)
            if true_domain.is_empty():
                return PropagationResult.conflict()
            
            if true_domain != true_val.domain:
                true_val.domain = true_domain
                changed.add(true_val)
        
        elif self._is_false(condition):
            # result must equal false_val
            result_domain = result.domain.intersect(false_val.domain)
            if result_domain.is_empty():
                return PropagationResult.conflict()
            
            if result_domain != result.domain:
                result.domain = result_domain
                changed.add(result)
            
            # Also constrain false_val to match result
            false_domain = false_val.domain.intersect(result.domain)
            if false_domain.is_empty():
                return PropagationResult.conflict()
            
            if false_domain != false_val.domain:
                false_val.domain = false_domain
                changed.add(false_val)
        
        # If condition is undetermined, we could try to infer it
        # from result, but that's complex and rarely useful
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def _is_true(self, var: Variable) -> bool:
        """Check if variable is definitely true (1)"""
        values = list(var.domain.values())
        return len(values) == 1 and values[0] == 1
    
    def _is_false(self, var: Variable) -> bool:
        """Check if variable is definitely false (0)"""
        values = list(var.domain.values())
        return len(values) == 1 and values[0] == 0
    
    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.condition_var, 
                self.true_val_var, self.false_val_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """
        Check if ternary expression is satisfied.
        
        Args:
            assignment: Variable assignments
            
        Returns:
            True if result = (cond ? true_val : false_val)
        """
        required = [self.result_var, self.condition_var,
                   self.true_val_var, self.false_val_var]
        
        if not all(v in assignment for v in required):
            return False
        
        result = assignment[self.result_var]
        condition = assignment[self.condition_var]
        true_val = assignment[self.true_val_var]
        false_val = assignment[self.false_val_var]
        
        expected = true_val if condition == 1 else false_val
        return result == expected
    
    def __repr__(self) -> str:
        return f"TernaryExpression({self.result_var} = {self.condition_var} ? {self.true_val_var} : {self.false_val_var})"
