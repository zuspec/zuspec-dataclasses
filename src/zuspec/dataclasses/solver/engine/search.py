"""Backtracking search engine for constraint solving."""

from typing import Dict, List, Optional, Set, Tuple
import random
from copy import deepcopy

from ..core.variable import Variable, VarKind
from ..core.domain import IntDomain
from ..engine.propagation import PropagationEngine
from ..propagators.base import PropagationStatus, Propagator
from ..randc.randc_manager import RandCManager, RandCConfig


class SearchState:
    """
    Represents the state of the search at a given point.
    Used for efficient backtracking via copy-on-write domains.
    """

    def __init__(self, variables: Dict[str, Variable],
                 decision_vars: Optional[Set[str]] = None):
        self.variables = variables
        self.assignment: Dict[str, int] = {}
        self.trail: List[Tuple[str, IntDomain]] = []  # Stack of (var_name, old_domain)
        # decision_vars: variables that the search assigns (rand vars).
        # All other vars in self.variables are tracked for backtracking only.
        self._decision_vars: Set[str] = (
            set(decision_vars) if decision_vars is not None else set(variables.keys())
        )

    def save_domain(self, var_name: str, domain: IntDomain) -> None:
        """Save current domain before modification."""
        self.trail.append((var_name, domain.copy()))

    def assign(self, var_name: str, value: int) -> None:
        """Assign a value to a variable."""
        self.assignment[var_name] = value
        var = self.variables[var_name]

        # Save old domain
        self.save_domain(var_name, var.domain)

        # Set to singleton domain
        var.domain = IntDomain([(value, value)], var.domain.width, var.domain.signed)

    def backtrack_to(self, trail_size: int) -> None:
        """Restore domains to a previous trail size."""
        while len(self.trail) > trail_size:
            var_name, old_domain = self.trail.pop()
            self.variables[var_name].domain = old_domain
            if var_name in self.assignment:
                del self.assignment[var_name]

    def is_complete(self) -> bool:
        """Check if all decision variables are assigned."""
        return self._decision_vars.issubset(self.assignment)

    def get_unassigned_variables(self) -> List[str]:
        """Get list of unassigned decision variable names."""
        return [name for name in self._decision_vars if name not in self.assignment]


class VariableOrderingHeuristic:
    """Base class for variable ordering heuristics."""
    
    def select_variable(self, state: SearchState, constraints_per_var: Dict[str, int]) -> Optional[str]:
        """Select next variable to assign."""
        raise NotImplementedError


class MinimumRemainingValues(VariableOrderingHeuristic):
    """MRV: Choose variable with smallest domain."""
    
    def select_variable(self, state: SearchState, constraints_per_var: Dict[str, int]) -> Optional[str]:
        unassigned = state.get_unassigned_variables()
        if not unassigned:
            return None
        
        # Choose variable with smallest domain
        return min(unassigned, key=lambda v: state.variables[v].domain.size())


class MostConstrainedVariable(VariableOrderingHeuristic):
    """Choose variable involved in most constraints."""
    
    def select_variable(self, state: SearchState, constraints_per_var: Dict[str, int]) -> Optional[str]:
        unassigned = state.get_unassigned_variables()
        if not unassigned:
            return None
        
        # Choose variable in most constraints
        return max(unassigned, key=lambda v: constraints_per_var.get(v, 0))


class MRVWithTiebreaking(VariableOrderingHeuristic):
    """MRV with most-constrained tiebreaking."""
    
    def select_variable(self, state: SearchState, constraints_per_var: Dict[str, int]) -> Optional[str]:
        unassigned = state.get_unassigned_variables()
        if not unassigned:
            return None
        
        # Find minimum domain size
        min_size = min(state.variables[v].domain.size() for v in unassigned)
        
        # Get all variables with minimum domain size
        mrv_vars = [v for v in unassigned if state.variables[v].domain.size() == min_size]
        
        if len(mrv_vars) == 1:
            return mrv_vars[0]
        
        # Tiebreak by most constrained
        return max(mrv_vars, key=lambda v: constraints_per_var.get(v, 0))


class ValueOrderingHeuristic:
    """Base class for value ordering heuristics."""
    
    def order_values(self, var_name: str, domain: IntDomain, state: SearchState) -> List[int]:
        """Order domain values for assignment."""
        raise NotImplementedError


class RandomValueOrdering(ValueOrderingHeuristic):
    """Random value ordering (default for randomization)."""
    
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
    
    def order_values(self, var_name: str, domain: IntDomain, state: SearchState) -> List[int]:
        values = list(domain.values())
        self.rng.shuffle(values)
        return values


class InOrderValueOrdering(ValueOrderingHeuristic):
    """In-order value ordering (smallest first)."""
    
    def order_values(self, var_name: str, domain: IntDomain, state: SearchState) -> List[int]:
        return list(domain.values())


class BacktrackingSearch:
    """
    DPLL-style backtracking search with constraint propagation.
    
    Implements complete search with:
    - Variable ordering heuristics
    - Value ordering heuristics
    - Constraint propagation at each node
    - Efficient backtracking with trail
    """
    
    def __init__(
        self,
        propagation_engine: PropagationEngine,
        var_heuristic: Optional[VariableOrderingHeuristic] = None,
        val_heuristic: Optional[ValueOrderingHeuristic] = None,
        max_backtracks: int = 100000,
        randc_manager: Optional[RandCManager] = None,
    ):
        """
        Initialize backtracking search.
        
        Args:
            propagation_engine: Engine for constraint propagation
            var_heuristic: Variable selection heuristic (default: MRV with tiebreaking)
            val_heuristic: Value ordering heuristic (default: random)
            max_backtracks: Maximum backtrack steps before giving up
            randc_manager: Manager for randc variables (default: create new)
        """
        self.engine = propagation_engine
        self.var_heuristic = var_heuristic or MRVWithTiebreaking()
        self.val_heuristic = val_heuristic or RandomValueOrdering()
        self.max_backtracks = max_backtracks
        self.randc_manager = randc_manager or RandCManager()
        
        # Statistics
        self.backtracks = 0
        self.nodes_explored = 0
        
        # Track constraints per variable
        self.constraints_per_var: Dict[str, int] = {}
        
        # Constraint version for randc reset detection
        self.constraint_version = 0
    
    def build_constraint_counts(self) -> None:
        """Build map of how many constraints affect each variable."""
        self.constraints_per_var.clear()
        for propagator in self.engine.propagators:
            for var_name in propagator.affected_variables():
                self.constraints_per_var[var_name] = \
                    self.constraints_per_var.get(var_name, 0) + 1
    
    def solve(self, variables: Dict[str, Variable]) -> Optional[Dict[str, int]]:
        """
        Find a satisfying assignment for the variables.

        Args:
            variables: Dictionary of decision variables to solve (rand/randc fields).
                       Additional propagated variables (reification bools, temps) are
                       taken from the engine and tracked for backtracking.

        Returns:
            Assignment dict if solution found, None if unsatisfiable
        """
        # Reset statistics
        self.backtracks = 0
        self.nodes_explored = 0

        # Build constraint counts
        self.build_constraint_counts()

        # Initial propagation
        result = self.engine.propagate()
        if result.status == PropagationStatus.CONFLICT:
            return None  # UNSAT

        # Build the full variable dict for backtracking state:
        # includes all engine variables (temp bool vars, consts, etc.)
        # so they are properly saved/restored on backtrack.
        all_vars = dict(self.engine.variables)
        # Merge in the rand variables (they may already be in engine.variables)
        all_vars.update(variables)

        # Create search state with all variables but only decision vars assigned
        state = SearchState(all_vars, decision_vars=set(variables.keys()))

        # Run backtracking search
        solution = self._search(state)

        if solution:
            return solution.assignment
        return None

    
    def _search(self, state: SearchState) -> Optional[SearchState]:
        """
        Recursive backtracking search.
        
        Args:
            state: Current search state
            
        Returns:
            SearchState with complete assignment if found, None otherwise
        """
        self.nodes_explored += 1
        
        # Check backtrack limit
        if self.backtracks >= self.max_backtracks:
            return None
        
        # Check if complete
        if state.is_complete():
            return state
        
        # Select variable
        var_name = self.var_heuristic.select_variable(state, self.constraints_per_var)
        if var_name is None:
            return None
        
        var = state.variables[var_name]
        
        # Check if domain is empty
        if var.domain.is_empty():
            return None
        
        # Handle randc variables specially
        if var.kind == VarKind.RANDC:
            return self._search_randc(state, var_name, var)
        
        # Order values
        values = self.val_heuristic.order_values(var_name, var.domain, state)
        
        # Try each value
        for value in values:
            # Save trail position for backtracking
            trail_size = len(state.trail)

            # Assign value
            state.assign(var_name, value)

            # Propagate constraints — pass trail callback so propagated
            # variable domains are saved for backtracking
            result = self.engine.propagate(trail_callback=state.save_domain)

            if result.status == PropagationStatus.CONFLICT:
                # Backtrack
                self.backtracks += 1
                state.backtrack_to(trail_size)
                continue

            # Recurse
            solution = self._search(state)

            if solution is not None:
                return solution

            # Backtrack
            self.backtracks += 1
            state.backtrack_to(trail_size)

        # No solution found
        return None
    
    def _search_randc(
        self,
        state: SearchState,
        var_name: str,
        var: Variable
    ) -> Optional[SearchState]:
        """
        Search for randc variable with permutation retry logic.
        
        Implements the randc retry loop from implementation plan:
        1. Get next value from permutation
        2. Try to solve with that value
        3. If conflict, try next value in permutation
        4. If permutation exhausted, generate new permutation
        5. After max retries, return None (UNSAT)
        
        Args:
            state: Current search state
            var_name: Name of randc variable
            var: The randc variable
            
        Returns:
            SearchState with solution, or None if no solution
        """
        # Try values from randc permutation
        while True:
            # Get next value from randc manager
            value = self.randc_manager.get_next_value(
                var,
                var.get_effective_domain(),
                self.constraint_version
            )
            
            if value is None:
                # Exhausted all permutations
                return None
            
            # Save trail position for backtracking
            trail_size = len(state.trail)

            # Assign value
            state.assign(var_name, value)

            # Propagate constraints
            result = self.engine.propagate(trail_callback=state.save_domain)
            
            if result.status == PropagationStatus.CONFLICT:
                # Conflict - backtrack and try next value in permutation
                self.backtracks += 1
                state.backtrack_to(trail_size)
                self.randc_manager.mark_value_failed(var)
                continue
            
            # No conflict - recurse
            solution = self._search(state)
            
            if solution is not None:
                # Success! Mark value as used
                self.randc_manager.mark_value_success(var, value)
                return solution
            
            # Backtrack and try next value
            self.backtracks += 1
            state.backtrack_to(trail_size)
            self.randc_manager.mark_value_failed(var)
    
    def get_statistics(self) -> Dict[str, int]:
        """Get search statistics."""
        return {
            'nodes_explored': self.nodes_explored,
            'backtracks': self.backtracks,
            'propagation_iterations': self.engine.get_stats().iterations,
            'propagations': self.engine.get_stats().propagations,
        }


class SolveBeforeOrderingHeuristic(VariableOrderingHeuristic):
    """
    Variable ordering that respects solve...before constraints.
    
    Builds topological order from solve...before directives,
    then applies fallback heuristic for variables at same level.
    """
    
    def __init__(
        self,
        solve_before_constraints: List[Tuple[str, str]],
        fallback_heuristic: Optional[VariableOrderingHeuristic] = None
    ):
        """
        Initialize solve...before ordering.
        
        Args:
            solve_before_constraints: List of (var1, var2) where var1 must be solved before var2
            fallback_heuristic: Heuristic for tiebreaking (default: MRV)
        """
        self.solve_before = solve_before_constraints
        self.fallback = fallback_heuristic or MinimumRemainingValues()
        self.topological_order: List[str] = []
        self.levels: Dict[str, int] = {}
    
    def build_topological_order(self, all_vars: Set[str]) -> None:
        """Build topological ordering from solve...before constraints."""
        from collections import defaultdict, deque
        
        # Build dependency graph
        in_degree = defaultdict(int)
        adj_list = defaultdict(list)
        
        for var1, var2 in self.solve_before:
            adj_list[var1].append(var2)
            in_degree[var2] += 1
        
        # Ensure all variables are in the graph
        for var in all_vars:
            if var not in in_degree:
                in_degree[var] = 0
        
        # Topological sort (Kahn's algorithm)
        queue = deque([v for v in all_vars if in_degree[v] == 0])
        order = []
        level = 0
        
        while queue:
            # Process all nodes at current level
            level_size = len(queue)
            for _ in range(level_size):
                node = queue.popleft()
                order.append(node)
                self.levels[node] = level
                
                for neighbor in adj_list[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            level += 1
        
        self.topological_order = order
    
    def select_variable(self, state: SearchState, constraints_per_var: Dict[str, int]) -> Optional[str]:
        unassigned = state.get_unassigned_variables()
        if not unassigned:
            return None
        
        # Build topological order if not done yet
        if not self.topological_order:
            self.build_topological_order(set(state.variables.keys()))
        
        # Find minimum level among unassigned variables
        min_level = min(self.levels.get(v, float('inf')) for v in unassigned)
        
        # Get all variables at minimum level
        min_level_vars = [v for v in unassigned if self.levels.get(v, float('inf')) == min_level]
        
        if len(min_level_vars) == 1:
            return min_level_vars[0]
        
        # Use fallback heuristic for tiebreaking
        # Create temporary state with only min_level_vars
        temp_state = SearchState({k: v for k, v in state.variables.items() if k in min_level_vars})
        temp_state.assignment = {k: v for k, v in state.assignment.items() if k in min_level_vars}
        
        return self.fallback.select_variable(temp_state, constraints_per_var)
