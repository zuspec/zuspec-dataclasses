"""Constraint propagation engine."""

from typing import Dict, List, Set, Optional
from collections import deque
from ..core.variable import Variable
from ..propagators.base import Propagator, PropagationStatus, PropagationResult


class PropagationStats:
    """Statistics for propagation execution."""
    
    def __init__(self):
        self.iterations = 0
        self.propagations = 0
        self.conflicts = 0
        self.propagations_per_constraint: Dict[Propagator, int] = {}
    
    def record_propagation(self, propagator: Propagator):
        """Record a propagation execution."""
        self.propagations += 1
        self.propagations_per_constraint[propagator] = \
            self.propagations_per_constraint.get(propagator, 0) + 1
    
    def record_conflict(self):
        """Record a conflict detection."""
        self.conflicts += 1
    
    def record_iteration(self):
        """Record a propagation iteration."""
        self.iterations += 1
    
    def __repr__(self) -> str:
        return (f"PropagationStats(iterations={self.iterations}, "
                f"propagations={self.propagations}, conflicts={self.conflicts})")


class PropagationEngine:
    """
    AC-3-style constraint propagation engine.
    
    Implements the core propagation loop that coordinates multiple propagators
    to achieve domain consistency (or detect conflicts).
    """
    
    def __init__(self, max_iterations: int = 10000):
        """
        Initialize the propagation engine.
        
        Args:
            max_iterations: Maximum iterations to prevent infinite loops
        """
        self.propagators: List[Propagator] = []
        self.variables: Dict[str, Variable] = {}
        self.max_iterations = max_iterations
        self.stats = PropagationStats()
        
        # Dependency tracking: variable name -> set of propagators
        self._var_to_propagators: Dict[str, Set[Propagator]] = {}
    
    def add_propagator(self, propagator: Propagator) -> None:
        """Add a propagator to the engine."""
        self.propagators.append(propagator)
        
        # Update dependency tracking
        for var_name in propagator.affected_variables():
            if var_name not in self._var_to_propagators:
                self._var_to_propagators[var_name] = set()
            self._var_to_propagators[var_name].add(propagator)
    
    def set_variables(self, variables: Dict[str, Variable]) -> None:
        """Set the variables to propagate on."""
        self.variables = variables
    
    def propagate(self) -> PropagationResult:
        """
        Run propagation until fixed point or conflict.
        
        Uses AC-3 algorithm:
        1. Initialize queue with all constraints
        2. Pop constraint and run propagator
        3. If domains changed, enqueue dependent constraints
        4. Repeat until fixed point or conflict
        
        Returns:
            PropagationResult with final status
        """
        # Reset stats
        self.stats = PropagationStats()
        
        # Initialize queue with all propagators
        queue = deque(self.propagators)
        in_queue = set(self.propagators)
        
        all_changed_vars = set()
        
        while queue and self.stats.iterations < self.max_iterations:
            self.stats.record_iteration()
            
            # Pop next propagator
            propagator = queue.popleft()
            in_queue.discard(propagator)
            
            # Run propagation
            self.stats.record_propagation(propagator)
            result = propagator.propagate(self.variables)
            
            if result.status == PropagationStatus.CONFLICT:
                # Conflict detected - propagation fails
                self.stats.record_conflict()
                return PropagationResult.conflict()
            
            elif result.status == PropagationStatus.CONSISTENT:
                # Domains changed - enqueue dependent propagators
                all_changed_vars.update(result.changed_vars)
                
                for var in result.changed_vars:
                    # Find propagators that depend on this variable
                    dependent_props = self._var_to_propagators.get(var.name, set())
                    
                    for dep_prop in dependent_props:
                        if dep_prop not in in_queue:
                            queue.append(dep_prop)
                            in_queue.add(dep_prop)
        
        # Check for cycle (max iterations exceeded)
        if self.stats.iterations >= self.max_iterations:
            # Treat as conflict (possible infinite loop)
            return PropagationResult.conflict()
        
        # Fixed point reached
        if all_changed_vars:
            return PropagationResult.consistent(all_changed_vars)
        return PropagationResult.fixed_point()
    
    def get_stats(self) -> PropagationStats:
        """Get propagation statistics."""
        return self.stats
    
    def clear(self) -> None:
        """Clear all propagators and reset state."""
        self.propagators.clear()
        self._var_to_propagators.clear()
        self.stats = PropagationStats()


class AdaptivePropagationEngine(PropagationEngine):
    """
    Adaptive propagation engine with multiple consistency levels.
    
    Starts with bounds consistency (fast) and escalates to domain
    consistency (precise) when needed.
    """
    
    class ConsistencyLevel:
        """Consistency levels for propagation."""
        BOUNDS = 1      # Only track min/max bounds
        DOMAIN = 2      # Track all domain values
    
    def __init__(self, max_iterations: int = 10000, 
                 escalation_threshold: int = 100):
        """
        Initialize adaptive engine.
        
        Args:
            max_iterations: Maximum iterations per level
            escalation_threshold: Propagations before escalating
        """
        super().__init__(max_iterations)
        self.consistency_level = self.ConsistencyLevel.BOUNDS
        self.escalation_threshold = escalation_threshold
    
    def propagate(self) -> PropagationResult:
        """
        Run adaptive propagation with level escalation.
        
        Starts with bounds consistency, escalates to domain consistency
        if progress is slow.
        """
        # Start with bounds consistency
        self.consistency_level = self.ConsistencyLevel.BOUNDS
        result = super().propagate()
        
        # Check if escalation is needed
        if result.status == PropagationStatus.CONSISTENT:
            if self.stats.propagations > self.escalation_threshold:
                # Escalate to domain consistency
                self.consistency_level = self.ConsistencyLevel.DOMAIN
                result = super().propagate()
        
        return result
    
    def get_consistency_level(self) -> int:
        """Get current consistency level."""
        return self.consistency_level


class WatchedLiteralEngine(PropagationEngine):
    """
    Propagation engine with watched literals optimization.
    
    Skips propagation when watched variables haven't changed,
    reducing unnecessary propagator executions.
    """
    
    def __init__(self, max_iterations: int = 10000):
        super().__init__(max_iterations)
        # Map propagator to its watched variables
        self._watched_vars: Dict[Propagator, Set[str]] = {}
    
    def add_propagator(self, propagator: Propagator) -> None:
        """Add propagator and initialize watched variables."""
        super().add_propagator(propagator)
        
        # Watch the first two variables (or all if fewer)
        affected = list(propagator.affected_variables())
        watched = set(affected[:2]) if len(affected) >= 2 else set(affected)
        self._watched_vars[propagator] = watched
    
    def propagate(self) -> PropagationResult:
        """
        Run propagation with watched literal optimization.
        
        Only executes propagators when their watched variables change.
        """
        self.stats = PropagationStats()
        
        # Track which variables changed in last iteration
        changed_vars: Set[str] = set(self.variables.keys())  # All changed initially
        
        all_changed_vars = set()
        
        while changed_vars and self.stats.iterations < self.max_iterations:
            self.stats.record_iteration()
            
            next_changed_vars = set()
            
            # Only propagate constraints whose watched variables changed
            for propagator in self.propagators:
                watched = self._watched_vars.get(propagator, set())
                
                # Check if any watched variable changed
                if not watched.intersection(changed_vars):
                    continue  # Skip - watched variables unchanged
                
                # Run propagation
                self.stats.record_propagation(propagator)
                result = propagator.propagate(self.variables)
                
                if result.status == PropagationStatus.CONFLICT:
                    self.stats.record_conflict()
                    return PropagationResult.conflict()
                
                elif result.status == PropagationStatus.CONSISTENT:
                    # Track changed variables
                    changed_var_names = {v.name for v in result.changed_vars}
                    all_changed_vars.update(result.changed_vars)
                    next_changed_vars.update(changed_var_names)
            
            # Update for next iteration
            changed_vars = next_changed_vars
            
            if not changed_vars:
                break  # Fixed point
        
        # Check for cycle
        if self.stats.iterations >= self.max_iterations:
            return PropagationResult.conflict()
        
        if all_changed_vars:
            return PropagationResult.consistent(all_changed_vars)
        return PropagationResult.fixed_point()
