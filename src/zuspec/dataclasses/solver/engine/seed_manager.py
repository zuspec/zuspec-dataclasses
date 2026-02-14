"""Random seed management for reproducible constraint solving.

Provides controlled random number generation for:
- Value ordering in search
- Variable ordering (when randomized)
- randc permutation generation
- Distribution-weighted sampling

All randomization uses this infrastructure to ensure:
- Reproducibility: same seed → same solution sequence
- Isolation: different objects can have independent seeds
- Predictability: seed changes are explicit and traceable
"""

import random
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class SeedState:
    """Captures the state of a random number generator.
    
    This allows saving and restoring RNG state for backtracking
    or reproducibility.
    """
    state: tuple
    
    @classmethod
    def from_random(cls, rng: random.Random) -> 'SeedState':
        """Capture current RNG state"""
        return cls(state=rng.getstate())
    
    def restore_to(self, rng: random.Random):
        """Restore RNG to this state"""
        rng.setstate(self.state)


class SeedManager:
    """
    Manages random seeds for constraint solving.
    
    Features:
    - Global seed control
    - Per-object seed isolation
    - Reproducible randomization
    - State capture for backtracking
    
    Usage:
        # Set global seed for reproducibility
        manager = SeedManager(global_seed=42)
        
        # Get RNG for a specific context
        rng = manager.get_rng("variable_ordering")
        value = rng.choice([1, 2, 3])
        
        # Different context, different sequence
        rng2 = manager.get_rng("value_selection")
        value2 = rng2.choice([4, 5, 6])
        
        # Same seed, same sequence
        manager2 = SeedManager(global_seed=42)
        rng3 = manager2.get_rng("variable_ordering")
        assert rng3.choice([1, 2, 3]) == value
    """
    
    def __init__(self, global_seed: Optional[int] = None):
        """
        Initialize seed manager.
        
        Args:
            global_seed: Master seed for all RNGs. If None, uses system randomness.
        """
        self.global_seed = global_seed
        
        # Master RNG for generating sub-seeds
        self._master_rng = random.Random(global_seed)
        
        # Context-specific RNGs
        self._rngs: Dict[str, random.Random] = {}
        
        # Context seed values for reproducibility
        self._context_seeds: Dict[str, int] = {}
    
    def get_rng(self, context: str) -> random.Random:
        """
        Get or create an RNG for a specific context.
        
        Each context gets its own independent RNG derived from
        the global seed. This ensures:
        - Reproducibility: same global seed → same per-context seeds
        - Isolation: contexts don't interfere with each other
        
        Args:
            context: Name of the context (e.g., "variable_ordering", "randc_x")
            
        Returns:
            Random number generator for this context
        """
        if context not in self._rngs:
            # Generate a seed for this context
            context_seed = self._master_rng.randint(0, 2**31 - 1)
            self._context_seeds[context] = context_seed
            
            # Create RNG for this context
            self._rngs[context] = random.Random(context_seed)
        
        return self._rngs[context]
    
    def reset_context(self, context: str):
        """
        Reset a context to its initial seed.
        
        Useful for:
        - Restarting a randomization sequence
        - Testing reproducibility
        
        Args:
            context: Context to reset
        """
        if context in self._context_seeds:
            seed = self._context_seeds[context]
            self._rngs[context] = random.Random(seed)
    
    def reset_all(self):
        """Reset all contexts to their initial seeds"""
        for context in list(self._context_seeds.keys()):
            self.reset_context(context)
    
    def set_context_seed(self, context: str, seed: int):
        """
        Explicitly set seed for a specific context.
        
        This overrides the seed derived from the global seed.
        Useful for fine-grained control over specific contexts.
        
        Args:
            context: Context to set seed for
            seed: Explicit seed value
        """
        self._context_seeds[context] = seed
        self._rngs[context] = random.Random(seed)
    
    def capture_state(self, context: str) -> SeedState:
        """
        Capture current state of a context's RNG.
        
        Useful for backtracking in search.
        
        Args:
            context: Context to capture
            
        Returns:
            Captured state
        """
        rng = self.get_rng(context)
        return SeedState.from_random(rng)
    
    def restore_state(self, context: str, state: SeedState):
        """
        Restore RNG to a captured state.
        
        Args:
            context: Context to restore
            state: Previously captured state
        """
        rng = self.get_rng(context)
        state.restore_to(rng)
    
    def get_context_info(self) -> Dict[str, Any]:
        """
        Get information about all contexts.
        
        Returns:
            Dictionary with context names and their seeds
        """
        return {
            "global_seed": self.global_seed,
            "contexts": dict(self._context_seeds),
            "num_contexts": len(self._rngs),
        }
    
    def __repr__(self) -> str:
        num_contexts = len(self._rngs)
        seed_str = str(self.global_seed) if self.global_seed is not None else "random"
        return f"SeedManager(global_seed={seed_str}, contexts={num_contexts})"


class PerObjectSeedManager:
    """
    Seed manager for per-object randomization.
    
    In PSS, each object being randomized can have its own seed,
    allowing independent randomization of different objects.
    
    Usage:
        manager = PerObjectSeedManager()
        
        # Object 1 with seed 10
        rng1 = manager.get_object_rng(obj_id=1, seed=10)
        
        # Object 2 with seed 20
        rng2 = manager.get_object_rng(obj_id=2, seed=20)
        
        # Independent randomization
        val1 = rng1.randint(0, 100)
        val2 = rng2.randint(0, 100)  # Independent of val1
    """
    
    def __init__(self):
        """Initialize per-object seed manager"""
        # Map from object ID to its SeedManager
        self._object_managers: Dict[Any, SeedManager] = {}
    
    def get_object_manager(self, obj_id: Any, seed: Optional[int] = None) -> SeedManager:
        """
        Get or create a SeedManager for a specific object.
        
        Args:
            obj_id: Unique identifier for the object
            seed: Optional seed for this object. If not provided, uses existing or creates new.
            
        Returns:
            SeedManager for this object
        """
        if obj_id not in self._object_managers:
            self._object_managers[obj_id] = SeedManager(global_seed=seed)
        elif seed is not None:
            # Update seed if explicitly provided
            self._object_managers[obj_id] = SeedManager(global_seed=seed)
        
        return self._object_managers[obj_id]
    
    def get_object_rng(self, obj_id: Any, context: str = "default", 
                      seed: Optional[int] = None) -> random.Random:
        """
        Get RNG for a specific object and context.
        
        Args:
            obj_id: Object identifier
            context: Context within the object (default: "default")
            seed: Optional seed for the object
            
        Returns:
            Random number generator
        """
        manager = self.get_object_manager(obj_id, seed)
        return manager.get_rng(context)
    
    def reset_object(self, obj_id: Any):
        """Reset all contexts for an object"""
        if obj_id in self._object_managers:
            self._object_managers[obj_id].reset_all()
    
    def reset_all_objects(self):
        """Reset all objects to their initial seeds"""
        for manager in self._object_managers.values():
            manager.reset_all()
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about all managed objects"""
        return {
            "num_objects": len(self._object_managers),
            "objects": {
                obj_id: manager.get_context_info()
                for obj_id, manager in self._object_managers.items()
            }
        }
    
    def __repr__(self) -> str:
        return f"PerObjectSeedManager(objects={len(self._object_managers)})"


# Global default seed manager for convenience
_default_seed_manager: Optional[SeedManager] = None


def get_default_seed_manager() -> SeedManager:
    """Get the global default seed manager"""
    global _default_seed_manager
    if _default_seed_manager is None:
        _default_seed_manager = SeedManager()
    return _default_seed_manager


def set_global_seed(seed: Optional[int]):
    """
    Set the global seed for all randomization.
    
    This affects the default seed manager used throughout the solver.
    
    Args:
        seed: Global seed value, or None for system randomness
    """
    global _default_seed_manager
    _default_seed_manager = SeedManager(global_seed=seed)


def reset_global_seed():
    """Reset to system randomness"""
    set_global_seed(None)
