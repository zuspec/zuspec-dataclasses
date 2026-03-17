"""Constraint system that holds all variables and constraints"""

from typing import Dict, List, Set, Optional
import networkx as nx

from .variable import Variable, VarKind
from .constraint import Constraint


class ConstraintSystem:
    """
    Container for variables, constraints, and their relationships.
    
    Maintains dependency graphs and metadata for constraint solving.
    """
    
    def __init__(self):
        # Variable storage
        self.variables: Dict[str, Variable] = {}
        
        # Constraint storage
        self.constraints: List[Constraint] = []
        
        # Array metadata for solution reconstruction: field_name -> {'size': N, 'element_names': [names]}
        self.array_metadata: Dict[str, dict] = {}
        
        # Dependency graph: edges from variables to variables
        # Edge (a, b) means "a depends on b" or "solve b before a"
        self.dependency_graph: nx.DiGraph = nx.DiGraph()
        
        # Connected components: groups of variables that share constraints
        # Each component can be solved independently
        self.connected_components: List[Set[Variable]] = []
        
        # Variables by kind
        self.randc_variables: List[Variable] = []
        
        # Solve order respecting solve...before constraints
        self.solve_order: List[Variable] = []
    
    def add_variable(self, variable: Variable):
        """
        Add a variable to the system.
        
        Args:
            variable: Variable to add
            
        Raises:
            ValueError: If variable with same name already exists
        """
        if variable.name in self.variables:
            raise ValueError(f"Variable {variable.name} already exists")
        
        self.variables[variable.name] = variable
        self.dependency_graph.add_node(variable)
        
        # Track randc variables
        if variable.kind == VarKind.RANDC:
            self.randc_variables.append(variable)
    
    def add_constraint(self, constraint: Constraint):
        """
        Add a constraint to the system.
        
        Args:
            constraint: Constraint to add
        """
        self.constraints.append(constraint)
    
    def add_ordering_constraint(self, before: Variable, after: Variable):
        """
        Add a solve...before ordering constraint.
        
        Args:
            before: Variable to solve before
            after: Variable to solve after
            
        Raises:
            ValueError: If this creates a cycle
        """
        # Add edge in dependency graph (from before -> after)
        # This means topological sort will put 'before' before 'after'
        self.dependency_graph.add_edge(before, after)
        
        # Check for cycles
        if not nx.is_directed_acyclic_graph(self.dependency_graph):
            # Remove the edge we just added
            self.dependency_graph.remove_edge(before, after)
            raise ValueError(
                f"Adding ordering constraint {before.name} before {after.name} "
                f"creates a circular dependency"
            )
        
        # Update the variable's order constraints list
        after.order_constraints.append(before)
    
    def compute_solve_order(self):
        """
        Compute topological sort of variables respecting solve...before constraints.
        
        Stores result in self.solve_order.
        """
        try:
            # Topological sort gives us the order
            self.solve_order = list(nx.topological_sort(self.dependency_graph))
        except nx.NetworkXError as e:
            raise ValueError(f"Cannot compute solve order: {e}")
    
    def compute_connected_components(self):
        """
        Compute connected components of variables based on constraints.
        
        Two variables are in the same component if they are connected through
        constraints (directly or transitively).
        
        Stores result in self.connected_components.
        """
        # Build undirected graph of variable relationships through constraints
        var_graph = nx.Graph()
        for var in self.variables.values():
            var_graph.add_node(var)
        
        # Add edges between variables that appear in same constraint
        for constraint in self.constraints:
            if not constraint.enabled:
                continue
            var_list = list(constraint.variables)
            for i in range(len(var_list)):
                for j in range(i + 1, len(var_list)):
                    var_graph.add_edge(var_list[i], var_list[j])
        
        # Find connected components
        self.connected_components = [
            set(component) 
            for component in nx.connected_components(var_graph)
        ]
    
    def get_variable(self, name: str) -> Optional[Variable]:
        """Get variable by name"""
        return self.variables.get(name)
    
    def get_constraints_for_variable(self, variable: Variable) -> List[Constraint]:
        """
        Get all constraints that reference a given variable.
        
        Args:
            variable: Variable to search for
            
        Returns:
            List of constraints that reference the variable
        """
        return [
            c for c in self.constraints 
            if c.enabled and variable in c.variables
        ]
    
    def get_enabled_constraints(self) -> List[Constraint]:
        """Get all enabled constraints"""
        return [c for c in self.constraints if c.enabled]
    
    def reset_randc_variables(self):
        """Reset all randc variables to start new cycles"""
        for var in self.randc_variables:
            if var.randc_state is not None:
                var.randc_state.reset_cycle()
    
    def __repr__(self) -> str:
        return (
            f"ConstraintSystem("
            f"vars={len(self.variables)}, "
            f"constraints={len(self.constraints)}, "
            f"components={len(self.connected_components)})"
        )

    def copy(self) -> 'ConstraintSystem':
        """Return a lightweight copy with fresh variable domains.

        Constraints and array_metadata are shared (they are immutable
        descriptions).  Variables are copied so each solve gets
        independent domains.
        """
        cs = ConstraintSystem.__new__(ConstraintSystem)
        cs.variables = {n: Variable(v.name, v.domain.copy(), v.kind)
                        for n, v in self.variables.items()}
        cs.constraints = self.constraints          # shared (immutable AST)
        cs.array_metadata = self.array_metadata    # shared
        cs.dependency_graph = self.dependency_graph
        cs.connected_components = self.connected_components
        cs.randc_variables = [cs.variables[v.name] for v in self.randc_variables
                              if v.name in cs.variables]
        cs.solve_order = self.solve_order
        return cs
