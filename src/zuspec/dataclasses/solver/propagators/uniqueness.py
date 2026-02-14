"""Uniqueness (AllDifferent) constraint propagator for PSS constraint solving.

Implements the 'unique' constraint: unique {v1, v2, ..., vn}
All variables must have different values.
"""

from typing import Dict, Set, List
from ..core.variable import Variable
from ..core.domain import IntDomain
from .base import Propagator, PropagationResult, PropagationStatus


class UniquePropagator(Propagator):
    """
    Propagator for uniqueness constraint: unique {v1, v2, ..., vn}
    
    Implements AllDifferent constraint with arc consistency.
    
    Propagation rules:
    1. When a variable is assigned, remove that value from all other variables
    2. If any variable has empty domain, conflict
    3. Early conflict detection: if n variables have < n values available, conflict
    
    This uses the basic AllDifferent algorithm with value removal.
    More advanced algorithms (e.g., Régin's) could be added for better propagation.
    """
    
    def __init__(self, var_names: List[str]):
        """
        Initialize uniqueness propagator.
        
        Args:
            var_names: List of variable names that must all be different
        """
        if len(var_names) < 2:
            raise ValueError("UniquePropagator requires at least 2 variables")
        
        self.var_names = var_names
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Propagate uniqueness constraint.
        
        Algorithm:
        1. For each assigned variable, remove its value from other variables
        2. Check for early conflict (pigeonhole principle)
        3. Return changed variables
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            PropagationResult with status and changed variables
        """
        # Check all variables exist
        if not all(name in variables for name in self.var_names):
            return PropagationResult.fixed_point()
        
        vars_list = [variables[name] for name in self.var_names]
        
        # Check for empty domains
        if any(v.domain.is_empty() for v in vars_list):
            return PropagationResult.conflict()
        
        changed = set()
        
        # Rule 1: Remove assigned values from other variables
        for i, var_i in enumerate(vars_list):
            if var_i.is_assigned():
                assigned_value = var_i.current_value
                
                # Remove this value from all other variables
                for j, var_j in enumerate(vars_list):
                    if i != j and not var_j.is_assigned():
                        old_domain = var_j.domain
                        
                        # Check if value is in domain
                        if assigned_value in list(var_j.domain.values()):
                            # Remove the value
                            new_domain = old_domain.copy()
                            new_domain.remove_value(assigned_value)
                            
                            if new_domain.is_empty():
                                return PropagationResult.conflict()
                            
                            if new_domain != old_domain:
                                var_j.domain = new_domain
                                changed.add(var_j)
        
        # Rule 2: Pigeonhole principle check
        # If n unassigned variables have fewer than n distinct values available, conflict
        unassigned_vars = [v for v in vars_list if not v.is_assigned()]
        
        if len(unassigned_vars) > 0:
            # Collect all available values
            all_values = set()
            for var in unassigned_vars:
                all_values.update(var.domain.values())
            
            # Check pigeonhole principle
            if len(all_values) < len(unassigned_vars):
                # Not enough values for all variables
                return PropagationResult.conflict()
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return set(self.var_names)
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """
        Check if uniqueness constraint is satisfied.
        
        All variables must have different values.
        
        Args:
            assignment: Variable assignments
            
        Returns:
            True if all variables have distinct values
        """
        if not all(name in assignment for name in self.var_names):
            return False
        
        values = [assignment[name] for name in self.var_names]
        
        # Check if all values are unique
        return len(values) == len(set(values))
    
    def __repr__(self) -> str:
        vars_str = ", ".join(self.var_names)
        return f"UniquePropagator({{{vars_str}}})"


class PairwiseUniquePropagator(Propagator):
    """
    Optimized propagator for uniqueness between two variables.
    
    This is a special case of UniquePropagator for better performance.
    """
    
    def __init__(self, var1: str, var2: str):
        """
        Initialize pairwise uniqueness propagator.
        
        Args:
            var1: First variable name
            var2: Second variable name
        """
        self.var1 = var1
        self.var2 = var2
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Propagate pairwise uniqueness: var1 != var2
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            PropagationResult
        """
        if self.var1 not in variables or self.var2 not in variables:
            return PropagationResult.fixed_point()
        
        v1 = variables[self.var1]
        v2 = variables[self.var2]
        
        if v1.domain.is_empty() or v2.domain.is_empty():
            return PropagationResult.conflict()
        
        changed = set()
        
        # If v1 is assigned, remove its value from v2
        if v1.is_assigned():
            value = v1.current_value
            if value in list(v2.domain.values()):
                old_domain = v2.domain
                new_domain = old_domain.copy()
                new_domain.remove_value(value)
                
                if new_domain.is_empty():
                    return PropagationResult.conflict()
                
                if new_domain != old_domain:
                    v2.domain = new_domain
                    changed.add(v2)
        
        # If v2 is assigned, remove its value from v1
        if v2.is_assigned():
            value = v2.current_value
            if value in list(v1.domain.values()):
                old_domain = v1.domain
                new_domain = old_domain.copy()
                new_domain.remove_value(value)
                
                if new_domain.is_empty():
                    return PropagationResult.conflict()
                
                if new_domain != old_domain:
                    v1.domain = new_domain
                    changed.add(v1)
        
        # Special case: both have singleton domains with same value
        v1_values = list(v1.domain.values())
        v2_values = list(v2.domain.values())
        
        if len(v1_values) == 1 and len(v2_values) == 1:
            if v1_values[0] == v2_values[0]:
                # Conflict: both must be same value
                return PropagationResult.conflict()
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return {self.var1, self.var2}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """Check if v1 != v2"""
        if not all(v in assignment for v in [self.var1, self.var2]):
            return False
        
        return assignment[self.var1] != assignment[self.var2]
    
    def __repr__(self) -> str:
        return f"PairwiseUnique({self.var1} != {self.var2})"
