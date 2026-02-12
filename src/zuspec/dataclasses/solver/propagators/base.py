"""Base classes for constraint propagators."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Set
from dataclasses import dataclass

from ..core.variable import Variable


class PropagationStatus(Enum):
    """Status of a propagation step."""
    CONSISTENT = 1      # Propagation succeeded, domains consistent
    CONFLICT = 2        # Propagation detected unsatisfiability
    FIXED_POINT = 3     # No changes made, fixed point reached


@dataclass
class PropagationResult:
    """Result of a propagation step."""
    status: PropagationStatus
    changed_vars: Set[Variable]
    
    @staticmethod
    def consistent(changed_vars: Set[Variable] = None) -> 'PropagationResult':
        """Create a consistent result."""
        return PropagationResult(PropagationStatus.CONSISTENT, changed_vars or set())
    
    @staticmethod
    def conflict() -> 'PropagationResult':
        """Create a conflict result."""
        return PropagationResult(PropagationStatus.CONFLICT, set())
    
    @staticmethod
    def fixed_point() -> 'PropagationResult':
        """Create a fixed point result."""
        return PropagationResult(PropagationStatus.FIXED_POINT, set())


class Propagator(ABC):
    """
    Abstract base class for constraint propagators.
    
    A propagator implements constraint propagation for a specific constraint type.
    It prunes variable domains to remove inconsistent values.
    """
    
    @abstractmethod
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """
        Perform constraint propagation.
        
        Args:
            variables: Dictionary of all variables in the constraint system
            
        Returns:
            PropagationResult indicating success/failure and changed variables
        """
        pass
    
    @abstractmethod
    def affected_variables(self) -> Set[str]:
        """
        Return the set of variable names this propagator can affect.
        
        Returns:
            Set of variable names
        """
        pass
    
    @abstractmethod
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """
        Check if constraint is satisfied by a complete assignment.
        
        Args:
            assignment: Complete variable assignment
            
        Returns:
            True if constraint is satisfied
        """
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.affected_variables()})"
