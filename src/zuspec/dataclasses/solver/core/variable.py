"""Variable and variable kind definitions"""

from enum import Enum
from typing import Optional, List
from .domain import Domain


class VarKind(Enum):
    """Variable kind enumeration"""
    RAND = "rand"      # Regular random variable
    RANDC = "randc"    # Random-cyclic variable
    STATE = "state"    # Non-random state variable


class RandCState:
    """State tracking for randc (random-cyclic) variables"""
    
    def __init__(self, domain_size: int):
        """
        Args:
            domain_size: Total size of the variable's domain
        """
        self.domain_size = domain_size
        self.used_values: List[int] = []
        self.cycle_complete = False
    
    def mark_used(self, value: int):
        """Mark a value as used in current cycle"""
        if value not in self.used_values:
            self.used_values.append(value)
        
        # Check if cycle is complete
        if len(self.used_values) >= self.domain_size:
            self.cycle_complete = True
    
    def reset_cycle(self):
        """Reset to start a new cycle"""
        self.used_values.clear()
        self.cycle_complete = False
    
    def get_available_domain(self, base_domain: Domain) -> Domain:
        """
        Returns domain with used values removed.
        
        Args:
            base_domain: Original domain for the variable
            
        Returns:
            Domain with used values excluded
        """
        result = base_domain.copy()
        for val in self.used_values:
            result.remove_value(val)
        return result


class Distribution:
    """Distribution constraint for a variable"""
    
    def __init__(self, dist_type: str, ranges: List[tuple], weights: List[int]):
        """
        Args:
            dist_type: Type of distribution ("dist", "dist_unique")
            ranges: List of (low, high) tuples or single values
            weights: Weight for each range
        """
        self.dist_type = dist_type
        self.ranges = ranges
        self.weights = weights


class Variable:
    """Represents a constraint variable"""
    
    def __init__(
        self,
        name: str,
        domain: Domain,
        kind: VarKind = VarKind.RAND,
        current_value: Optional[int] = None
    ):
        """
        Args:
            name: Variable name
            domain: Domain of possible values
            kind: Variable kind (RAND, RANDC, STATE)
            current_value: Current assigned value (if any)
        """
        self.name = name
        self.domain = domain
        self.kind = kind
        self.current_value = current_value
        
        # Ordering constraints - variables to solve before this one
        self.order_constraints: List['Variable'] = []
        
        # Distribution constraint
        self.distribution: Optional[Distribution] = None
        
        # Random-cyclic state (only for RANDC variables)
        self.randc_state: Optional[RandCState] = None
        if kind == VarKind.RANDC:
            self.randc_state = RandCState(domain.size())
    
    def is_assigned(self) -> bool:
        """Returns True if variable has been assigned a value"""
        return self.current_value is not None
    
    def assign(self, value: int):
        """
        Assign a value to this variable.
        
        Args:
            value: Value to assign
            
        Raises:
            ValueError: If value is not in domain
        """
        # Verify value is in domain
        if value not in list(self.domain.values()):
            raise ValueError(f"Value {value} not in domain for variable {self.name}")
        
        self.current_value = value
        
        # Update randc state
        if self.randc_state is not None:
            self.randc_state.mark_used(value)
    
    def unassign(self):
        """Remove assignment from variable"""
        self.current_value = None
    
    def get_effective_domain(self) -> Domain:
        """
        Returns the effective domain for this variable.
        
        For randc variables, returns domain with used values removed.
        For other variables, returns the base domain.
        """
        if self.randc_state is not None:
            return self.randc_state.get_available_domain(self.domain)
        return self.domain
    
    def __repr__(self) -> str:
        value_str = f"={self.current_value}" if self.current_value is not None else ""
        return f"Variable({self.name}:{self.kind.value}{value_str}, domain={self.domain})"
    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Variable):
            return False
        return self.name == other.name
