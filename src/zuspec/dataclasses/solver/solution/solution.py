"""Solution representation and validation"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..core.variable import Variable
from ..core.constraint import Constraint
from ..propagators.base import Propagator


class SolutionStatus(Enum):
    """Solution status enumeration"""
    SATISFIABLE = "satisfiable"      # Solution found
    UNSATISFIABLE = "unsatisfiable"  # No solution exists
    TIMEOUT = "timeout"              # Search timed out
    ERROR = "error"                  # Error during solving


@dataclass
class Solution:
    """
    Represents a solution to a constraint problem.
    
    Contains variable assignments and validation status.
    """
    
    status: SolutionStatus
    assignments: Dict[str, int]  # variable_name -> value
    errors: List[str]  # Error messages for UNSAT/ERROR
    statistics: Dict[str, Any]  # Search statistics
    
    def is_satisfiable(self) -> bool:
        """Check if solution is satisfiable"""
        return self.status == SolutionStatus.SATISFIABLE
    
    def get_value(self, var_name: str) -> Optional[int]:
        """
        Get value for a variable.
        
        Args:
            var_name: Name of variable
            
        Returns:
            Assigned value, or None if not assigned
        """
        return self.assignments.get(var_name)
    
    def __repr__(self) -> str:
        if self.status == SolutionStatus.SATISFIABLE:
            assignments_str = ", ".join(
                f"{name}={value}" for name, value in sorted(self.assignments.items())
            )
            return f"Solution(SAT: {assignments_str})"
        else:
            return f"Solution({self.status.value.upper()})"


class SolutionGenerator:
    """
    Generates and validates solutions for constraint systems.
    
    Integrates backtracking search with randc support and validation.
    """
    
    def __init__(self):
        """Initialize solution generator"""
        pass
    
    def create_solution(
        self,
        status: SolutionStatus,
        assignments: Optional[Dict[str, int]] = None,
        errors: Optional[List[str]] = None,
        statistics: Optional[Dict[str, Any]] = None
    ) -> Solution:
        """
        Create a Solution object.
        
        Args:
            status: Solution status
            assignments: Variable assignments (for SAT)
            errors: Error messages (for UNSAT/ERROR)
            statistics: Search statistics
            
        Returns:
            Solution object
        """
        return Solution(
            status=status,
            assignments=assignments or {},
            errors=errors or [],
            statistics=statistics or {}
        )
    
    def validate_solution(
        self,
        solution: Solution,
        variables: Dict[str, Variable],
        propagators: List[Propagator]
    ) -> bool:
        """
        Validate that a solution satisfies all constraints.
        
        Args:
            solution: Solution to validate
            variables: Variable dictionary
            propagators: List of constraint propagators
            
        Returns:
            True if solution is valid, False otherwise
        """
        if not solution.is_satisfiable():
            return False
        
        # Check all variables are assigned
        for var_name in variables:
            if var_name not in solution.assignments:
                solution.errors.append(f"Variable {var_name} not assigned")
                return False
        
        # Check all assignments are in domains
        for var_name, value in solution.assignments.items():
            if var_name not in variables:
                solution.errors.append(f"Unknown variable {var_name} in solution")
                return False
            
            var = variables[var_name]
            if value not in list(var.domain.values()):
                solution.errors.append(
                    f"Value {value} for {var_name} not in domain {var.domain}"
                )
                return False
        
        # Validate against propagators - check if constraints are satisfied
        # For full validation, we'd need to check using is_satisfied() if available
        for propagator in propagators:
            # Check if propagator has is_satisfied method
            if hasattr(propagator, 'is_satisfied'):
                if not propagator.is_satisfied(solution.assignments):
                    solution.errors.append(
                        f"Constraint violated: {propagator}"
                    )
                    return False
        
        return True
    
    def _get_propagator_variables(self, propagator: Propagator) -> List[str]:
        """
        Extract variable names from a propagator.
        
        Args:
            propagator: Propagator to extract variables from
            
        Returns:
            List of variable names
        """
        # Most propagators have result_var and operand attributes
        vars = []
        if hasattr(propagator, 'result_var'):
            vars.append(propagator.result_var)
        if hasattr(propagator, 'lhs_var'):
            vars.append(propagator.lhs_var)
        if hasattr(propagator, 'rhs_var'):
            vars.append(propagator.rhs_var)
        if hasattr(propagator, 'var1'):
            vars.append(propagator.var1)
        if hasattr(propagator, 'var2'):
            vars.append(propagator.var2)
        return vars
    
    def format_unsat_report(
        self,
        solution: Solution,
        variables: Dict[str, Variable]
    ) -> str:
        """
        Generate a detailed UNSAT report.
        
        Args:
            solution: Unsatisfiable solution
            variables: Variable dictionary
            
        Returns:
            Formatted error report
        """
        if solution.status != SolutionStatus.UNSATISFIABLE:
            return "Solution is not UNSAT"
        
        report = ["UNSATISFIABLE: No solution found", ""]
        
        # Add error messages
        if solution.errors:
            report.append("Errors:")
            for error in solution.errors:
                report.append(f"  - {error}")
            report.append("")
        
        # Add statistics
        if solution.statistics:
            report.append("Search Statistics:")
            for key, value in solution.statistics.items():
                report.append(f"  {key}: {value}")
            report.append("")
        
        # Add variable domains (for debugging)
        report.append("Variable Domains:")
        for var_name, var in sorted(variables.items()):
            domain_str = str(var.domain)
            report.append(f"  {var_name}: {domain_str}")
        
        return "\n".join(report)
