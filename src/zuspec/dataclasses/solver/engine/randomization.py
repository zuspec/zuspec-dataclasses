"""Randomized search order for uniform solution sampling.

Provides variable and value ordering heuristics that use randomization
to generate uniformly distributed solutions (when no distribution constraints
are present).

Key features:
- Randomized variable ordering (respects solve...before)
- Randomized value selection from domains
- Controlled by SeedManager for reproducibility
- Can be combined with other heuristics (e.g., MRV + random tiebreaking)
"""

import random
from typing import Dict, List, Set, Optional
from ..core.variable import Variable
from ..core.domain import IntDomain
from .search import VariableOrderingHeuristic, ValueOrderingHeuristic
from .seed_manager import SeedManager


class RandomizedVariableOrdering(VariableOrderingHeuristic):
    """
    Randomized variable ordering for uniform solution sampling.
    
    Shuffles unassigned variables to explore search space randomly.
    This provides uniform sampling when combined with randomized value ordering.
    
    Note: If solve...before constraints exist, use SolveBeforeRandomizedOrdering
    instead to respect the ordering requirements.
    
    Usage:
        seed_manager = SeedManager(global_seed=42)
        heuristic = RandomizedVariableOrdering(seed_manager)
        search = BacktrackingSearch(engine, var_heuristic=heuristic)
    """
    
    def __init__(self, seed_manager: Optional[SeedManager] = None, context: str = "var_order"):
        """
        Args:
            seed_manager: Seed manager for reproducible randomization
            context: Context name for RNG (default: "var_order")
        """
        self.seed_manager = seed_manager
        self.context = context
    
    def select_variable(self, state: 'SearchState', constraints_per_var: Dict[str, int]) -> Optional[str]:
        """
        Select next variable randomly.
        
        Args:
            state: Current search state
            constraints_per_var: Constraints per variable (unused)
            
        Returns:
            Randomly selected unassigned variable, or None if all assigned
        """
        unassigned = state.get_unassigned_variables()
        
        if not unassigned:
            return None
        
        # Randomly select from unassigned
        if self.seed_manager:
            rng = self.seed_manager.get_rng(self.context)
        else:
            rng = random.Random()
        
        return rng.choice(unassigned)
    
    def order_variables(self, variables: Dict[str, Variable], assigned: Set[str]) -> List[str]:
        """
        Compute complete random ordering of unassigned variables.
        
        Args:
            variables: All variables
            assigned: Already assigned variables to exclude
            
        Returns:
            Randomly shuffled list of unassigned variable names
        """
        unassigned = [name for name in variables.keys() if name not in assigned]
        
        if self.seed_manager:
            rng = self.seed_manager.get_rng(self.context)
        else:
            rng = random.Random()
        
        rng.shuffle(unassigned)
        return unassigned
    
    def __repr__(self) -> str:
        return f"RandomizedVariableOrdering(context={self.context})"


class RandomizedValueOrdering(ValueOrderingHeuristic):
    """
    Randomized value ordering for uniform solution sampling.
    
    Samples values randomly from a variable's domain. Combined with
    randomized variable ordering, this provides uniform sampling over
    the solution space (when no distribution constraints exist).

    For large domains (> *max_values* entries) a random subset is sampled
    instead of enumerating all values.  This bounds the per-variable search
    width and prevents catastrophic backtracking on problems with chained
    arithmetic constraints where domains can easily reach tens-of-thousands
    of values.

    The default *max_values=256* works well for typical randomisation
    problems (many valid solutions per domain value).  Increase it for
    tightly-constrained problems where only a small fraction of domain
    values are locally consistent.

    Usage:
        seed_manager = SeedManager(global_seed=42)
        heuristic = RandomizedValueOrdering(seed_manager)
        search = BacktrackingSearch(variables, engine, val_order=heuristic)
    """

    # Maximum number of values tried per variable before giving up at this level.
    DEFAULT_MAX_VALUES = 256

    def __init__(
        self,
        seed_manager: Optional[SeedManager] = None,
        context: str = "val_order",
        max_values: Optional[int] = None,
    ):
        """
        Args:
            seed_manager: Seed manager for reproducible randomization
            context: Context name for RNG (default: "val_order")
            max_values: Maximum candidate values per variable assignment attempt.
                        Defaults to DEFAULT_MAX_VALUES.  Pass ``None`` to use
                        the default; pass a large value (e.g. ``float("inf")``)
                        to enumerate all values (old behaviour – not recommended
                        for large domains).
        """
        self.seed_manager = seed_manager
        self.context = context
        self.max_values = max_values if max_values is not None else self.DEFAULT_MAX_VALUES

    def order_values(self, variable_or_name, state_or_assigned=None, state=None) -> List[int]:
        """
        Return a randomly ordered list of candidate values from the domain.

        Supports two call signatures:
        1. order_values(variable: Variable, assigned: Set[str]) - for tests
        2. order_values(var_name: str, domain: IntDomain, state: SearchState) - for search

        Args:
            variable_or_name: Variable object or variable name string
            state_or_assigned: SearchState or assigned set
            state: SearchState (for 3-arg signature)

        Returns:
            Randomly shuffled list of up to *max_values* values from domain
        """
        # Handle both signatures
        if isinstance(variable_or_name, Variable):
            # Signature 1: order_values(variable, assigned)
            domain = variable_or_name.domain
        else:
            # Signature 2: order_values(var_name, domain, state)
            domain = state_or_assigned

        if self.seed_manager:
            rng = self.seed_manager.get_rng(self.context)
        else:
            rng = random.Random()

        domain_size = domain.size()
        max_v = self.max_values

        # For small or unbounded-max domains enumerate everything; for large
        # domains use efficient random sampling to cap search width.
        if domain_size <= max_v or max_v <= 0:
            values = list(domain.values())
            rng.shuffle(values)
        else:
            from ..core.domain import IntDomain as _IntDomain
            if isinstance(domain, _IntDomain):
                values = domain.random_sample(rng, max_v)
            else:
                # Fallback for non-IntDomain types (e.g. EnumDomain)
                values = list(domain.values())
                rng.shuffle(values)
                values = values[:max_v]

        return values


class MRVWithRandomTiebreaking(VariableOrderingHeuristic):
    """
    Minimum Remaining Values with randomized tiebreaking.
    
    Combines MRV heuristic (fail-first strategy) with random tiebreaking
    when multiple variables have the same domain size. This provides:
    - Efficiency from MRV (prune search space early)
    - Randomization for solution diversity
    
    Usage:
        seed_manager = SeedManager(global_seed=42)
        heuristic = MRVWithRandomTiebreaking(seed_manager)
    """
    
    def __init__(self, seed_manager: Optional[SeedManager] = None, 
                 context: str = "mrv_tiebreak"):
        """
        Args:
            seed_manager: Seed manager for reproducible randomization
            context: Context name for RNG
        """
        self.seed_manager = seed_manager
        self.context = context
    
    def select_variable(self, state: 'SearchState', constraints_per_var: Dict[str, int]) -> Optional[str]:
        """
        Select variable using MRV with random tiebreaking.
        
        Args:
            state: Current search state
            constraints_per_var: Constraints per variable (unused)
            
        Returns:
            Variable with minimum remaining values, ties broken randomly
        """
        # Get unassigned variables with their domain sizes
        unassigned = state.get_unassigned_variables()
        
        if not unassigned:
            return None
        
        # Find minimum domain size
        min_size = min(state.variables[name].domain.size() for name in unassigned)
        
        # Get all variables with min size (ties)
        candidates = [name for name in unassigned 
                     if state.variables[name].domain.size() == min_size]
        
        # If single candidate, return it
        if len(candidates) == 1:
            return candidates[0]
        
        # Break ties randomly
        if self.seed_manager:
            rng = self.seed_manager.get_rng(self.context)
        else:
            rng = random.Random()
        
        return rng.choice(candidates)
    
    def order_variables(self, variables: Dict[str, Variable], assigned: Set[str]) -> List[str]:
        """
        Compute complete ordering using MRV with random tiebreaking.
        
        Args:
            variables: All variables
            assigned: Already assigned variables to exclude
            
        Returns:
            List of variable names ordered by MRV (ties broken randomly)
        """
        unassigned = [name for name in variables.keys() if name not in assigned]
        
        if not unassigned:
            return []
        
        # Get RNG for consistent tiebreaking
        if self.seed_manager:
            rng = self.seed_manager.get_rng(self.context)
        else:
            rng = random.Random()
        
        # Sort by domain size, using random values for tiebreaking
        # Assign random tiebreaker to each variable
        var_with_tie = [(name, variables[name].domain.size(), rng.random()) 
                        for name in unassigned]
        
        # Sort by size (ascending), then by random tiebreaker
        var_with_tie.sort(key=lambda x: (x[1], x[2]))
        
        return [name for name, _, _ in var_with_tie]
    
    def __repr__(self) -> str:
        return f"MRVWithRandomTiebreaking(context={self.context})"


class SolveBeforeRandomizedOrdering(VariableOrderingHeuristic):
    """
    Randomized ordering that respects solve...before constraints.
    
    Critical for correct distribution semantics (Phase 3.4):
    - Variables in solve-before chains are ordered deterministically
    - Within unconstrained groups, order is randomized
    - This ensures earlier variables are sampled uniformly regardless of
      constraints on later variables
    
    Example:
        solve x before y before z;  // Order: x, y, z (deterministic)
        rand w;                      // Can be before, between, or after
        
        With randomization, might get: [x, w, y, z] or [w, x, y, z] or [x, y, w, z]
        But never [y, x, z, w] (violates solve-before)
    
    Usage:
        seed_manager = SeedManager(global_seed=42)
        heuristic = SolveBeforeRandomizedOrdering(
            solve_order={"x": 0, "y": 1, "z": 2},
            seed_manager=seed_manager
        )
    """
    
    def __init__(self, solve_order: Optional[Dict[str, int]] = None,
                 seed_manager: Optional[SeedManager] = None,
                 context: str = "solve_before_rand"):
        """
        Args:
            solve_order: Map from variable name to order index (lower = earlier)
            seed_manager: Seed manager for reproducible randomization
            context: Context name for RNG
        """
        self.solve_order = solve_order or {}
        self.seed_manager = seed_manager
        self.context = context
    
    def select_variable(self, state: 'SearchState', constraints_per_var: Dict[str, int]) -> Optional[str]:
        """
        Select variable respecting solve-before, randomizing unconstrained.
        
        Algorithm:
        1. Separate variables into ordered (solve-before) and unordered
        2. If ordered variables remain, return the one with lowest index
        3. Otherwise, randomly select from unordered
        
        Args:
            state: Current search state
            constraints_per_var: Constraints per variable (unused)
            
        Returns:
            Next variable respecting solve-before with randomization
        """
        unassigned = state.get_unassigned_variables()
        
        if not unassigned:
            return None
        
        # Separate ordered and unordered
        ordered = []
        unordered = []
        
        for name in unassigned:
            if name in self.solve_order:
                ordered.append((self.solve_order[name], name))
            else:
                unordered.append(name)
        
        # If we have ordered variables, return the one with lowest index
        if ordered:
            ordered.sort(key=lambda x: x[0])
            return ordered[0][1]
        
        # Otherwise, randomly select from unordered
        if unordered:
            if self.seed_manager:
                rng = self.seed_manager.get_rng(self.context)
            else:
                rng = random.Random()
            return rng.choice(unordered)
        
        return None
    
    def order_variables(self, variables: Dict[str, Variable], assigned: Set[str]) -> List[str]:
        """
        Compute complete ordering respecting solve-before.
        
        Args:
            variables: All variables
            assigned: Already assigned variables to exclude
            
        Returns:
            List of variable names with solve-before constraints respected,
            unordered variables randomized
        """
        unassigned = [name for name in variables.keys() if name not in assigned]
        
        if not unassigned:
            return []
        
        # Separate ordered and unordered
        ordered = []
        unordered = []
        
        for name in unassigned:
            if name in self.solve_order:
                ordered.append((self.solve_order[name], name))
            else:
                unordered.append(name)
        
        # Sort ordered by index
        ordered.sort(key=lambda x: x[0])
        ordered_names = [name for _, name in ordered]
        
        # Shuffle unordered
        if self.seed_manager:
            rng = self.seed_manager.get_rng(self.context)
        else:
            rng = random.Random()
        
        rng.shuffle(unordered)
        
        # Return ordered first, then unordered
        return ordered_names + unordered
    
    def __repr__(self) -> str:
        num_ordered = len(self.solve_order)
        return f"SolveBeforeRandomizedOrdering(ordered_vars={num_ordered}, context={self.context})"


class AdaptiveRandomizedOrdering(VariableOrderingHeuristic):
    """
    Adaptive ordering: MRV for constrained, random for unconstrained.
    
    Strategy:
    - If a variable has small domain (< threshold), use MRV (fail-first)
    - If a variable has large domain, randomize (exploration)
    - Provides both efficiency and solution diversity
    
    Usage:
        seed_manager = SeedManager(global_seed=42)
        heuristic = AdaptiveRandomizedOrdering(
            domain_threshold=10,
            seed_manager=seed_manager
        )
    """
    
    def __init__(self, domain_threshold: int = 10,
                 seed_manager: Optional[SeedManager] = None,
                 context: str = "adaptive_rand"):
        """
        Args:
            domain_threshold: Domains <= this size use MRV, larger randomized
            seed_manager: Seed manager for reproducible randomization
            context: Context name for RNG
        """
        self.threshold = domain_threshold
        self.seed_manager = seed_manager
        self.context = context
    
    def select_variable(self, state: 'SearchState', constraints_per_var: Dict[str, int]) -> Optional[str]:
        """
        Adaptively select variable.
        
        Strategy:
        - If there are constrained variables (domain <= threshold), use MRV
        - Otherwise, randomly select from unconstrained variables
        
        Args:
            state: Current search state
            constraints_per_var: Constraints per variable (unused)
            
        Returns:
            Adaptively selected variable
        """
        unassigned = state.get_unassigned_variables()
        
        if not unassigned:
            return None
        
        # Separate constrained (small domain) and unconstrained (large domain)
        constrained = []
        unconstrained = []
        
        for name in unassigned:
            size = state.variables[name].domain.size()
            if size <= self.threshold:
                constrained.append((name, size))
            else:
                unconstrained.append(name)
        
        # If we have constrained variables, use MRV
        if constrained:
            min_size = min(size for _, size in constrained)
            candidates = [name for name, size in constrained if size == min_size]
            
            if len(candidates) == 1:
                return candidates[0]
            
            # Break ties randomly
            if self.seed_manager:
                rng = self.seed_manager.get_rng(self.context)
            else:
                rng = random.Random()
            return rng.choice(candidates)
        
        # Otherwise, randomly select from unconstrained
        if unconstrained:
            if self.seed_manager:
                rng = self.seed_manager.get_rng(self.context)
            else:
                rng = random.Random()
            return rng.choice(unconstrained)
        
        return None
    
    def order_variables(self, variables: Dict[str, Variable], assigned: Set[str]) -> List[str]:
        """
        Compute complete ordering using adaptive strategy.
        
        Args:
            variables: All variables
            assigned: Already assigned variables to exclude
            
        Returns:
            List of variable names ordered by adaptive strategy
        """
        unassigned = [name for name in variables.keys() if name not in assigned]
        
        if not unassigned:
            return []
        
        # Get RNG
        if self.seed_manager:
            rng = self.seed_manager.get_rng(self.context)
        else:
            rng = random.Random()
        
        # Separate constrained and unconstrained
        constrained = []
        unconstrained = []
        
        for name in unassigned:
            size = variables[name].domain.size()
            if size <= self.threshold:
                constrained.append((name, size, rng.random()))
            else:
                unconstrained.append((name, rng.random()))
        
        # Sort constrained by size (MRV), then random tiebreaker
        constrained.sort(key=lambda x: (x[1], x[2]))
        constrained_names = [name for name, _, _ in constrained]
        
        # Sort unconstrained by random tiebreaker
        unconstrained.sort(key=lambda x: x[1])
        unconstrained_names = [name for name, _ in unconstrained]
        
        # Constrained first (MRV), then unconstrained
        return constrained_names + unconstrained_names
    
    def __repr__(self) -> str:
        return f"AdaptiveRandomizedOrdering(threshold={self.threshold}, context={self.context})"
