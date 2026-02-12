"""Constraint dependency analysis with connected component decomposition."""

from typing import Dict, Set, List, Tuple
from collections import defaultdict
from ..core.constraint import Constraint
from ..core.variable import Variable


class DependencyAnalyzer:
    """
    Analyzes constraint dependencies and decomposes into connected components.
    """
    
    def __init__(self):
        self.constraint_vars: List[Set[str]] = []  # Variables per constraint
        self.var_constraints: Dict[str, Set[int]] = defaultdict(set)  # Constraints per variable
        self.components: List[Set[int]] = []  # Connected components (constraint indices)
        self.ordering: List[int] = []  # Evaluation order
    
    def analyze(self, constraints: List[Constraint], variables: Dict[str, Variable]) -> None:
        """Build dependency graph and decompose into components."""
        self.constraint_vars = []
        self.var_constraints = defaultdict(set)
        
        # Build bipartite graph: constraints <-> variables
        for idx, constraint in enumerate(constraints):
            # Get variables from the constraint
            vars_in_constraint = constraint.variables if hasattr(constraint, 'variables') else set()
            var_names = {v.name if hasattr(v, 'name') else str(v) for v in vars_in_constraint}
            
            self.constraint_vars.append(var_names)
            
            for var_name in var_names:
                self.var_constraints[var_name].add(idx)
        
        # Decompose into connected components
        self._find_connected_components(len(constraints))
        
        # Compute evaluation order
        self._compute_ordering()
    
    def _find_connected_components(self, num_constraints: int) -> None:
        """
        Use Union-Find to decompose constraints into connected components.
        Two constraints are in the same component if they share variables.
        """
        parent = list(range(num_constraints))
        rank = [0] * num_constraints
        
        def find(x: int) -> int:
            if parent[x] != x:
                parent[x] = find(parent[x])  # Path compression
            return parent[x]
        
        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px == py:
                return
            # Union by rank
            if rank[px] < rank[py]:
                parent[px] = py
            elif rank[px] > rank[py]:
                parent[py] = px
            else:
                parent[py] = px
                rank[px] += 1
        
        # Union constraints that share variables
        for var_name, constraint_indices in self.var_constraints.items():
            indices = list(constraint_indices)
            for i in range(len(indices) - 1):
                union(indices[i], indices[i + 1])
        
        # Group constraints by component
        component_map: Dict[int, Set[int]] = defaultdict(set)
        for idx in range(num_constraints):
            root = find(idx)
            component_map[root].add(idx)
        
        self.components = list(component_map.values())
    
    def _compute_ordering(self) -> None:
        """
        Compute constraint evaluation order.
        For now, use simple topological order within components.
        """
        # Within each component, constraints can be evaluated in any order
        # Future: respect solve...before directives
        self.ordering = []
        for component in self.components:
            self.ordering.extend(sorted(component))
    
    def get_components(self) -> List[Set[int]]:
        """Get list of independent constraint groups (components)."""
        return self.components
    
    def get_ordering(self) -> List[int]:
        """Get constraint evaluation order."""
        return self.ordering
    
    def get_component_for_constraint(self, constraint_idx: int) -> int:
        """Get component index for a constraint."""
        for comp_idx, component in enumerate(self.components):
            if constraint_idx in component:
                return comp_idx
        return -1
    
    def get_variables_for_component(self, component_idx: int) -> Set[str]:
        """Get all variables involved in a component."""
        if component_idx < 0 or component_idx >= len(self.components):
            return set()
        
        variables = set()
        for constraint_idx in self.components[component_idx]:
            if constraint_idx < len(self.constraint_vars):
                variables.update(self.constraint_vars[constraint_idx])
        return variables
    
    def handle_solve_before(self, ordering_constraints: List[Tuple[int, int]]) -> None:
        """
        Handle solve...before ordering directives.
        ordering_constraints: list of (constraint_i, constraint_j) where i must be solved before j.
        """
        # Build dependency graph
        in_degree = defaultdict(int)
        adj_list = defaultdict(list)
        
        for i, j in ordering_constraints:
            adj_list[i].append(j)
            in_degree[j] += 1
        
        # Topological sort (Kahn's algorithm)
        queue = [i for i in self.ordering if in_degree[i] == 0]
        new_ordering = []
        
        while queue:
            node = queue.pop(0)
            new_ordering.append(node)
            
            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(new_ordering) == len(self.ordering):
            self.ordering = new_ordering
        else:
            # Cycle detected - keep original ordering
            pass
