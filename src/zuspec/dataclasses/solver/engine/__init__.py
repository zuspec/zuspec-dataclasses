"""Solver engine components."""

from .propagation import (
    PropagationEngine,
    AdaptivePropagationEngine,
    WatchedLiteralEngine,
    PropagationStats,
)
from .search import (
    BacktrackingSearch,
    SearchState,
    VariableOrderingHeuristic,
    ValueOrderingHeuristic,
    MinimumRemainingValues,
    MostConstrainedVariable,
    MRVWithTiebreaking,
    RandomValueOrdering,
    InOrderValueOrdering,
    SolveBeforeOrderingHeuristic,
)
from .seed_manager import (
    SeedManager,
    SeedState,
    PerObjectSeedManager,
    get_default_seed_manager,
    set_global_seed,
    reset_global_seed,
)
from .randomization import (
    RandomizedVariableOrdering,
    RandomizedValueOrdering,
    MRVWithRandomTiebreaking,
    SolveBeforeRandomizedOrdering,
    AdaptiveRandomizedOrdering,
)

__all__ = [
    # Propagation
    "PropagationEngine",
    "AdaptivePropagationEngine",
    "WatchedLiteralEngine",
    "PropagationStats",
    # Search
    "BacktrackingSearch",
    "SearchState",
    "VariableOrderingHeuristic",
    "ValueOrderingHeuristic",
    "MinimumRemainingValues",
    "MostConstrainedVariable",
    "MRVWithTiebreaking",
    "RandomValueOrdering",
    "InOrderValueOrdering",
    "SolveBeforeOrderingHeuristic",
    # Seed Management
    "SeedManager",
    "SeedState",
    "PerObjectSeedManager",
    "get_default_seed_manager",
    "set_global_seed",
    "reset_global_seed",
    # Randomization
    "RandomizedVariableOrdering",
    "RandomizedValueOrdering",
    "MRVWithRandomTiebreaking",
    "SolveBeforeRandomizedOrdering",
    "AdaptiveRandomizedOrdering",
]
