"""Set membership constraint propagator for PSS constraint solving.

Implements the 'inside' operator: var inside {values, [lo:hi], ...}
"""

from typing import Dict, Set, List, Tuple, Union
from ..core.variable import Variable
from ..core.domain import IntDomain
from .base import Propagator, PropagationResult, PropagationStatus


class InSetPropagator(Propagator):
    """
    Propagator for set membership: var inside {set_elements}
    
    Set elements can be:
    - Individual values: {1, 5, 10}
    - Ranges: {[0:10], [20:30]}
    - Mix: {1, 5, [10:20], 42}
    
    Propagation:
    - Intersect variable domain with set domain
    - If empty result, conflict
    - If domain changed, mark as changed
    """
    
    def __init__(
        self,
        var_name: str,
        set_elements: List[Union[int, Tuple[int, int]]],
        width: int = 32,
        signed: bool = False,
        negated: bool = False
    ):
        """
        Initialize set membership propagator.
        
        Args:
            var_name: Name of variable to check
            set_elements: List of values or (low, high) tuples
            width: Bit width for domain construction
            signed: Whether domain is signed
            negated: If True, implements !(var inside {...})
        """
        self.var_name = var_name
        self.set_elements = set_elements
        self.width = width
        self.signed = signed
        self.negated = negated
        
        # Build set domain from elements
        self.set_domain = self._build_set_domain()
    
    def _build_set_domain(self) -> IntDomain:
        """
        Build domain from set elements.
        
        Returns:
            IntDomain containing all values in the set
        """
        intervals = []
        
        for element in self.set_elements:
            if isinstance(element, tuple):
                # Range [lo:hi]
                low, high = element
                intervals.append((low, high))
            else:
                # Single value
                intervals.append((element, element))
        
        # Merge overlapping intervals
        if intervals:
            intervals.sort()
            merged = [intervals[0]]
            
            for low, high in intervals[1:]:
                last_low, last_high = merged[-1]
                
                # Check if overlapping or adjacent
                if low <= last_high + 1:
                    # Merge
                    merged[-1] = (last_low, max(last_high, high))
                else:
                    # Separate interval
                    merged.append((low, high))
            
            return IntDomain(merged, self.width, self.signed)
        else:
            # Empty set
            return IntDomain([], self.width, self.signed)
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Propagate set membership constraint.
        
        For 'var inside {set}':
            - Intersect var domain with set domain
        
        For '!(var inside {set})':
            - Remove set domain values from var domain
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            PropagationResult with status and changed variables
        """
        if self.var_name not in variables:
            return PropagationResult.fixed_point()
        
        var = variables[self.var_name]
        
        if var.domain.is_empty():
            return PropagationResult.conflict()
        
        old_domain = var.domain
        
        if self.negated:
            # !(var inside {set}) - remove set values from var domain
            new_domain = old_domain.copy()
            for value in self.set_domain.values():
                new_domain.remove_value(value)
        else:
            # var inside {set} - intersect with set domain
            new_domain = old_domain.intersect(self.set_domain)
        
        if new_domain.is_empty():
            return PropagationResult.conflict()
        
        if new_domain != old_domain:
            var.domain = new_domain
            return PropagationResult.consistent({var})
        
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return {self.var_name}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """
        Check if set membership is satisfied.
        
        Args:
            assignment: Variable assignments
            
        Returns:
            True if constraint satisfied
        """
        if self.var_name not in assignment:
            return False
        
        value = assignment[self.var_name]
        in_set = value in list(self.set_domain.values())
        
        # Apply negation if needed
        return (not in_set) if self.negated else in_set
    
    def __repr__(self) -> str:
        neg_str = "!" if self.negated else ""
        return f"InSetPropagator({neg_str}{self.var_name} inside {self.set_elements})"


class RangeConstraintPropagator(Propagator):
    """
    Propagator for simple range constraints: low <= var <= high
    
    This is a simpler, optimized version of InSetPropagator for single ranges.
    """
    
    def __init__(
        self,
        var_name: str,
        low: int,
        high: int,
        width: int = 32,
        signed: bool = False
    ):
        """
        Initialize range constraint propagator.
        
        Args:
            var_name: Name of variable
            low: Lower bound (inclusive)
            high: Upper bound (inclusive)
            width: Bit width
            signed: Whether signed
        """
        self.var_name = var_name
        self.low = low
        self.high = high
        self.width = width
        self.signed = signed
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Propagate range constraint.
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            PropagationResult
        """
        if self.var_name not in variables:
            return PropagationResult.fixed_point()
        
        var = variables[self.var_name]
        
        if var.domain.is_empty():
            return PropagationResult.conflict()
        
        old_domain = var.domain
        
        # Intersect with range
        range_domain = IntDomain([(self.low, self.high)], self.width, self.signed)
        new_domain = old_domain.intersect(range_domain)
        
        if new_domain.is_empty():
            return PropagationResult.conflict()
        
        if new_domain != old_domain:
            var.domain = new_domain
            return PropagationResult.consistent({var})
        
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return {self.var_name}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """Check if range constraint is satisfied"""
        if self.var_name not in assignment:
            return False
        
        value = assignment[self.var_name]
        return self.low <= value <= self.high
    
    def __repr__(self) -> str:
        return f"RangeConstraint({self.low} <= {self.var_name} <= {self.high})"
