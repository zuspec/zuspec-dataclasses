"""Constraint base class and related types"""

from abc import ABC
from typing import Set, Optional, Dict, Any


class SourceLocation:
    """Source location information for error reporting"""
    
    def __init__(self, file: str, line: int, column: int = 0):
        self.file = file
        self.line = line
        self.column = column
    
    def __repr__(self) -> str:
        if self.column:
            return f"{self.file}:{self.line}:{self.column}"
        return f"{self.file}:{self.line}"


class Constraint(ABC):
    """Base class for all constraints"""
    
    _next_id = 0
    
    def __init__(
        self,
        variables: Set['Variable'],
        soft: bool = False,
        weight: Optional[float] = None,
        enabled: bool = True,
        source_location: Optional[SourceLocation] = None
    ):
        """
        Args:
            variables: Set of variables referenced by this constraint
            soft: True if this is a soft constraint
            weight: Weight for soft constraint priority (higher = more important)
            enabled: Whether constraint is currently enabled
            source_location: Source location for error reporting
        """
        # Generate unique ID
        self.id = f"c{Constraint._next_id}"
        Constraint._next_id += 1
        
        self.variables = variables
        self.soft = soft
        self.weight = weight
        self.enabled = enabled
        self.source_location = source_location
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """
        Check if constraint is satisfied by given assignment.
        
        Args:
            assignment: Map from variable name to assigned value
            
        Returns:
            True if constraint is satisfied
        """
        raise NotImplementedError("Subclasses must implement is_satisfied")
    
    def get_referenced_variables(self) -> Set['Variable']:
        """Returns set of variables referenced by this constraint"""
        return self.variables
    
    def __repr__(self) -> str:
        var_names = [v.name for v in self.variables]
        soft_str = " [soft]" if self.soft else ""
        return f"{self.__class__.__name__}({self.id}, vars={var_names}{soft_str})"
