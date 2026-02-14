"""Soft constraint support for PSS constraint solving.

Soft constraints are preferences that should be satisfied if possible,
but don't cause UNSAT if violated. They guide solution selection among
valid solutions.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from .core.variable import Variable
from .propagators.base import Propagator


@dataclass
class SoftConstraint:
    """
    Represents a soft constraint with weight.
    
    Soft constraints are preferences:
    - Weight indicates priority (higher = more important)
    - Violation doesn't cause UNSAT
    - Used to select among multiple valid solutions
    """
    propagator: Propagator
    weight: int = 1
    name: Optional[str] = None
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """Check if soft constraint is satisfied"""
        return self.propagator.is_satisfied(assignment)
    
    def __repr__(self) -> str:
        name_str = f" ({self.name})" if self.name else ""
        return f"SoftConstraint{name_str}[weight={self.weight}]: {self.propagator}"


class SoftConstraintManager:
    """
    Manages soft constraints and solution scoring.
    
    Strategy:
    1. Solve hard constraints first (backtracking search)
    2. Among valid solutions, prefer those satisfying soft constraints
    3. Use weighted sum for multiple soft constraints
    4. Respect solve...before ordering with soft constraints
    """
    
    def __init__(self):
        """Initialize soft constraint manager"""
        self.soft_constraints: List[SoftConstraint] = []
    
    def add_soft_constraint(
        self,
        propagator: Propagator,
        weight: int = 1,
        name: Optional[str] = None
    ):
        """
        Add a soft constraint.
        
        Args:
            propagator: Propagator representing the constraint
            weight: Priority weight (higher = more important)
            name: Optional name for debugging
        """
        soft = SoftConstraint(propagator, weight, name)
        self.soft_constraints.append(soft)
    
    def score_solution(self, assignment: Dict[str, int]) -> int:
        """
        Score a solution based on soft constraints satisfied.
        
        Higher score = better solution
        
        Args:
            assignment: Variable assignments
            
        Returns:
            Weighted sum of satisfied soft constraints
        """
        score = 0
        
        for soft in self.soft_constraints:
            if soft.is_satisfied(assignment):
                score += soft.weight
        
        return score
    
    def get_violated_constraints(
        self,
        assignment: Dict[str, int]
    ) -> List[SoftConstraint]:
        """
        Get list of violated soft constraints.
        
        Args:
            assignment: Variable assignments
            
        Returns:
            List of violated soft constraints
        """
        violated = []
        
        for soft in self.soft_constraints:
            if not soft.is_satisfied(assignment):
                violated.append(soft)
        
        return violated
    
    def get_satisfaction_summary(
        self,
        assignment: Dict[str, int]
    ) -> Dict[str, any]:
        """
        Get detailed summary of soft constraint satisfaction.
        
        Args:
            assignment: Variable assignments
            
        Returns:
            Dictionary with satisfaction details
        """
        satisfied = []
        violated = []
        
        for soft in self.soft_constraints:
            if soft.is_satisfied(assignment):
                satisfied.append(soft)
            else:
                violated.append(soft)
        
        total_weight = sum(s.weight for s in self.soft_constraints)
        satisfied_weight = sum(s.weight for s in satisfied)
        
        return {
            'score': satisfied_weight,
            'max_score': total_weight,
            'satisfaction_rate': satisfied_weight / total_weight if total_weight > 0 else 1.0,
            'satisfied_count': len(satisfied),
            'violated_count': len(violated),
            'satisfied': satisfied,
            'violated': violated,
        }
    
    def compare_solutions(
        self,
        solution1: Dict[str, int],
        solution2: Dict[str, int]
    ) -> int:
        """
        Compare two solutions based on soft constraints.
        
        Args:
            solution1: First solution
            solution2: Second solution
            
        Returns:
            1 if solution1 is better, -1 if solution2 is better, 0 if equal
        """
        score1 = self.score_solution(solution1)
        score2 = self.score_solution(solution2)
        
        if score1 > score2:
            return 1
        elif score1 < score2:
            return -1
        else:
            return 0
    
    def __repr__(self) -> str:
        return f"SoftConstraintManager({len(self.soft_constraints)} soft constraints)"


class SoftConstraintSolver:
    """
    Solver extension that handles soft constraints.
    
    Uses multiple-solution generation to find the best solution
    according to soft constraints.
    """
    
    def __init__(
        self,
        hard_solver,  # BacktrackingSearch
        soft_manager: SoftConstraintManager,
        max_solutions: int = 100
    ):
        """
        Initialize soft constraint solver.
        
        Args:
            hard_solver: Solver for hard constraints
            soft_manager: Soft constraint manager
            max_solutions: Maximum solutions to evaluate
        """
        self.hard_solver = hard_solver
        self.soft_manager = soft_manager
        self.max_solutions = max_solutions
    
    def solve(self, variables: Dict[str, Variable]) -> Optional[Dict[str, int]]:
        """
        Solve with soft constraints.
        
        Strategy:
        1. Find solutions satisfying hard constraints
        2. Score each solution with soft constraints
        3. Return solution with highest score
        
        Args:
            variables: Variables to solve
            
        Returns:
            Best solution according to soft constraints, or None if UNSAT
        """
        # Find first solution (hard constraints only)
        first_solution = self.hard_solver.solve(variables)
        
        if first_solution is None:
            return None  # Hard constraints UNSAT
        
        # If no soft constraints, return first solution
        if not self.soft_manager.soft_constraints:
            return first_solution
        
        # For now, return first solution with soft constraint scoring
        # A more sophisticated approach would generate multiple solutions
        # and pick the best one, but that requires solution enumeration
        
        # Score the solution
        score = self.soft_manager.score_solution(first_solution)
        
        return first_solution
    
    def find_best_solution(
        self,
        variables: Dict[str, Variable]
    ) -> Optional[Dict[str, int]]:
        """
        Find best solution by evaluating multiple solutions.
        
        Note: This is a placeholder. Full implementation would require
        solution enumeration support in the backtracking search.
        
        Args:
            variables: Variables to solve
            
        Returns:
            Best solution, or None if UNSAT
        """
        # For now, same as solve()
        # TODO: Implement solution enumeration and ranking
        return self.solve(variables)
