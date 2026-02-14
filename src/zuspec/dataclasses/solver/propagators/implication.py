"""Implication constraint propagator for PSS constraint solving.

Implements the implication operator: condition -> consequence
Using 3-valued logic for proper constraint propagation.
"""

from typing import Dict, Set, Optional
from ..core.variable import Variable
from ..core.domain import IntDomain
from .base import Propagator, PropagationResult, PropagationStatus


class ImplicationPropagator(Propagator):
    """
    Propagator for implication constraints: condition -> consequence
    
    Semantics:
    - If condition is definitely true (domain = {1}), enforce consequence
    - If consequence is definitely false (domain = {0}), enforce !condition
    - Otherwise, wait for more information (3-valued logic)
    
    This implements logical implication:
        A -> B  ≡  !A || B
    
    Truth table:
        A | B | A->B
        0 | 0 |  1
        0 | 1 |  1
        1 | 0 |  0
        1 | 1 |  1
    """
    
    def __init__(self, condition_var: str, consequence_var: str):
        """
        Initialize implication propagator.
        
        Args:
            condition_var: Name of condition variable (boolean: 0 or 1)
            consequence_var: Name of consequence variable (boolean: 0 or 1)
        """
        self.condition_var = condition_var
        self.consequence_var = consequence_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Propagate implication constraint.
        
        Rules:
        1. If condition = 1 (true), then consequence must be 1 (true)
        2. If consequence = 0 (false), then condition must be 0 (false)
        3. Otherwise, no propagation (wait for more info)
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            PropagationResult with status and changed variables
        """
        if self.condition_var not in variables or self.consequence_var not in variables:
            return PropagationResult.fixed_point()
        
        cond = variables[self.condition_var]
        cons = variables[self.consequence_var]
        
        # Check for empty domains
        if cond.domain.is_empty() or cons.domain.is_empty():
            return PropagationResult.conflict()
        
        changed = set()
        
        # Rule 1: If condition is definitely true (domain = {1}), enforce consequence = 1
        if self._is_definitely_true(cond.domain):
            # Consequence must be true
            new_domain = cons.domain.intersect(
                IntDomain([(1, 1)], cons.domain.width, cons.domain.signed)
            )
            if new_domain.is_empty():
                return PropagationResult.conflict()
            if new_domain != cons.domain:
                cons.domain = new_domain
                changed.add(cons)
        
        # Rule 2: If consequence is definitely false (domain = {0}), enforce !condition
        elif self._is_definitely_false(cons.domain):
            # Condition must be false
            new_domain = cond.domain.intersect(
                IntDomain([(0, 0)], cond.domain.width, cond.domain.signed)
            )
            if new_domain.is_empty():
                return PropagationResult.conflict()
            if new_domain != cond.domain:
                cond.domain = new_domain
                changed.add(cond)
        
        # Rule 3: Both could be true or false - wait for assignment
        # No propagation needed
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def _is_definitely_true(self, domain: IntDomain) -> bool:
        """Check if domain is definitely true (only contains 1)"""
        values = list(domain.values())
        return len(values) == 1 and values[0] == 1
    
    def _is_definitely_false(self, domain: IntDomain) -> bool:
        """Check if domain is definitely false (only contains 0)"""
        values = list(domain.values())
        return len(values) == 1 and values[0] == 0
    
    def affected_variables(self) -> Set[str]:
        return {self.condition_var, self.consequence_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """
        Check if implication is satisfied in assignment.
        
        A -> B is satisfied if A is false OR B is true
        """
        if not all(v in assignment for v in [self.condition_var, self.consequence_var]):
            return False
        
        cond = assignment[self.condition_var]
        cons = assignment[self.consequence_var]
        
        # A -> B  ≡  !A || B
        return (cond == 0) or (cons == 1)
    
    def __repr__(self) -> str:
        return f"ImplicationPropagator({self.condition_var} -> {self.consequence_var})"


class ConditionalImplicationPropagator(Propagator):
    """
    Propagator for conditional implications with actual constraints.
    
    Example: (op == WRITE) -> (addr < 0x1000)
    
    This is more complex than simple boolean implication because
    the condition and consequence are actual constraints that need
    to be checked/enforced.
    """
    
    def __init__(
        self,
        condition_constraint: Propagator,
        consequence_constraint: Propagator,
        condition_vars: Set[str],
        consequence_vars: Set[str]
    ):
        """
        Initialize conditional implication propagator.
        
        Args:
            condition_constraint: Propagator for condition
            consequence_constraint: Propagator for consequence
            condition_vars: Variables involved in condition
            consequence_vars: Variables involved in consequence
        """
        self.condition_constraint = condition_constraint
        self.consequence_constraint = consequence_constraint
        self.condition_vars = condition_vars
        self.consequence_vars = consequence_vars
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Propagate conditional implication.
        
        Logic:
        1. Check if condition is definitely satisfied
        2. If yes, propagate consequence constraint
        3. If consequence is definitely unsatisfied, we have a problem
           (but in practice, this is handled by the search)
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            PropagationResult with status and changed variables
        """
        # Check if all condition variables are assigned
        condition_assigned = all(
            var in variables and variables[var].is_assigned()
            for var in self.condition_vars
        )
        
        if condition_assigned:
            # Check if condition is satisfied
            assignment = {
                var: variables[var].current_value
                for var in self.condition_vars
            }
            
            if self.condition_constraint.is_satisfied(assignment):
                # Condition is true, enforce consequence
                result = self.consequence_constraint.propagate(variables)
                return result
        
        # Condition not yet determined, no propagation
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return self.condition_vars | self.consequence_vars
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """
        Check if conditional implication is satisfied.
        
        Satisfied if condition is false OR consequence is true.
        """
        # Check if condition is satisfied
        cond_vars_assigned = all(v in assignment for v in self.condition_vars)
        if not cond_vars_assigned:
            return False  # Can't determine yet
        
        cond_assignment = {v: assignment[v] for v in self.condition_vars}
        condition_satisfied = self.condition_constraint.is_satisfied(cond_assignment)
        
        if not condition_satisfied:
            # Condition is false, implication is satisfied
            return True
        
        # Condition is true, check consequence
        cons_vars_assigned = all(v in assignment for v in self.consequence_vars)
        if not cons_vars_assigned:
            return False  # Can't determine yet
        
        cons_assignment = {v: assignment[v] for v in self.consequence_vars}
        return self.consequence_constraint.is_satisfied(cons_assignment)
    
    def __repr__(self) -> str:
        return f"ConditionalImplication({self.condition_constraint} -> {self.consequence_constraint})"
