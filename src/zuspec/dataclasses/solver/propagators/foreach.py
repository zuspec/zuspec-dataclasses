"""Foreach constraint expansion for PSS constraint solving.

Implements expansion of foreach loops over arrays into individual constraints.
"""

from typing import Dict, List, Callable, Set, Optional
from ..core.variable import Variable
from .base import Propagator, PropagationResult


class ForeachExpander:
    """
    Expands foreach loops into individual constraints.
    
    Example PSS:
        foreach (data[i]) {
            if (i < len)
                data[i] != 0;
        }
    
    Expands to:
        data[0] != 0;  // if 0 < len
        data[1] != 0;  // if 1 < len
        ...
    """
    
    @staticmethod
    def expand_foreach(
        array_var_names: List[str],
        constraint_generator: Callable[[int, str], Optional[Propagator]],
        start_index: int = 0
    ) -> List[Propagator]:
        """
        Expand foreach loop into individual constraints.
        
        Args:
            array_var_names: List of array element variable names
            constraint_generator: Function (index, var_name) -> Propagator
                                 Returns None to skip index
            start_index: Starting index for loop (default: 0)
            
        Returns:
            List of propagators for each array element
        """
        propagators = []
        
        for i, var_name in enumerate(array_var_names, start=start_index):
            prop = constraint_generator(i, var_name)
            if prop is not None:
                propagators.append(prop)
        
        return propagators
    
    @staticmethod
    def expand_nested_foreach(
        outer_array_names: List[str],
        inner_array_names: List[str],
        constraint_generator: Callable[[int, str, int, str], Optional[Propagator]]
    ) -> List[Propagator]:
        """
        Expand nested foreach loops.
        
        Example PSS:
            foreach (outer[i]) {
                foreach (inner[j]) {
                    outer[i] != inner[j];
                }
            }
        
        Args:
            outer_array_names: Outer loop variable names
            inner_array_names: Inner loop variable names
            constraint_generator: Function (i, outer_var, j, inner_var) -> Propagator
            
        Returns:
            List of propagators for all combinations
        """
        propagators = []
        
        for i, outer_var in enumerate(outer_array_names):
            for j, inner_var in enumerate(inner_array_names):
                prop = constraint_generator(i, outer_var, j, inner_var)
                if prop is not None:
                    propagators.append(prop)
        
        return propagators


class ForeachConstraintGroup(Propagator):
    """
    Groups expanded foreach constraints for efficient propagation.
    
    This allows treating a foreach expansion as a single logical unit
    while propagating all individual constraints.
    """
    
    def __init__(
        self,
        propagators: List[Propagator],
        name: Optional[str] = None
    ):
        """
        Initialize foreach constraint group.
        
        Args:
            propagators: List of expanded propagators
            name: Optional name for debugging
        """
        self.propagators = propagators
        self.name = name
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Propagate all constraints in the group.
        
        Args:
            variables: Dictionary of variables
            
        Returns:
            Combined propagation result
        """
        all_changed = set()
        
        for prop in self.propagators:
            result = prop.propagate(variables)
            
            if result.is_conflict():
                return result
            
            all_changed.update(result.changed_vars)
        
        if all_changed:
            return PropagationResult.consistent(all_changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        """Get all variables affected by any constraint in the group"""
        affected = set()
        for prop in self.propagators:
            affected.update(prop.affected_variables())
        return affected
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """Check if all constraints in the group are satisfied"""
        return all(p.is_satisfied(assignment) for p in self.propagators)
    
    def __repr__(self) -> str:
        name_str = f" ({self.name})" if self.name else ""
        return f"ForeachConstraintGroup{name_str}[{len(self.propagators)} constraints]"


# Helper functions for common foreach patterns

def create_array_constraint_foreach(
    array_var_names: List[str],
    constraint_type: type,
    **constraint_kwargs
) -> ForeachConstraintGroup:
    """
    Create foreach constraint applying same constraint to all array elements.
    
    Example:
        # foreach (arr[i]) arr[i] > 0
        create_array_constraint_foreach(
            ["arr_0", "arr_1", "arr_2"],
            GreaterThanPropagator,
            rhs_var="zero"
        )
    
    Args:
        array_var_names: Array element variable names
        constraint_type: Propagator class to instantiate
        **constraint_kwargs: Arguments to pass to propagator constructor
        
    Returns:
        ForeachConstraintGroup containing all constraints
    """
    def generator(i: int, var_name: str) -> Optional[Propagator]:
        # Replace placeholder in kwargs with actual var_name
        kwargs = constraint_kwargs.copy()
        for key, value in kwargs.items():
            if value == "{i}":
                kwargs[key] = var_name
        
        return constraint_type(**kwargs)
    
    propagators = ForeachExpander.expand_foreach(array_var_names, generator)
    return ForeachConstraintGroup(propagators, name="array_constraint")


def create_unique_array_foreach(
    array_var_names: List[str]
) -> ForeachConstraintGroup:
    """
    Create foreach constraint enforcing uniqueness in array.
    
    Example:
        # foreach (arr[i]) foreach (arr[j]) if (i < j) arr[i] != arr[j]
        
    This is equivalent to unique {arr[0], arr[1], ...}
    but demonstrates foreach expansion.
    
    Args:
        array_var_names: Array element variable names
        
    Returns:
        ForeachConstraintGroup with pairwise uniqueness constraints
    """
    from .uniqueness import PairwiseUniquePropagator
    
    def generator(i: int, outer_var: str, j: int, inner_var: str) -> Optional[Propagator]:
        if i < j:
            return PairwiseUniquePropagator(outer_var, inner_var)
        return None
    
    propagators = ForeachExpander.expand_nested_foreach(
        array_var_names,
        array_var_names,
        generator
    )
    
    return ForeachConstraintGroup(propagators, name="unique_array")
