"""Enhanced randc (random-cyclic) variable management"""

import random
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from ..core.variable import Variable, VarKind
from ..core.domain import Domain


@dataclass
class RandCConfig:
    """Configuration for randc behavior"""
    max_permutation_retries: int = 100  # Max permutations before giving up
    seed: Optional[int] = None  # Seed for reproducibility
    constraint_version: int = 0  # Version counter for constraint changes


class RandCManager:
    """
    Manages randc (random-cyclic) variables with enhanced retry logic.
    
    Key features from implementation plan:
    1. Controlled RNG for reproducibility
    2. Permutation generation and tracking
    3. Retry loop: try each permutation value, skip on conflict
    4. Reset on constraint changes
    5. Exhaust permutations before returning UNSAT
    """
    
    def __init__(self, config: Optional[RandCConfig] = None):
        """
        Args:
            config: Configuration for randc behavior
        """
        self.config = config or RandCConfig()
        self.rng = random.Random(self.config.seed)
        
        # Track state per randc variable
        # variable_name -> (current_permutation, position, constraint_version)
        self.state: Dict[str, tuple] = {}
        
        # Track retry count for giving up
        self.retry_counts: Dict[str, int] = {}
    
    def get_next_value(
        self,
        variable: Variable,
        available_domain: Domain,
        constraint_version: int
    ) -> Optional[int]:
        """
        Get next value from randc permutation for a variable.
        
        Implements the retry loop logic from implementation plan:
        - Generate permutation from available domain
        - Return next value in permutation
        - Track position for subsequent calls
        - Reset if constraints changed
        
        Args:
            variable: The randc variable
            available_domain: Domain after constraint propagation
            constraint_version: Current constraint version number
            
        Returns:
            Next value from permutation, or None if permutation exhausted
        """
        if variable.kind != VarKind.RANDC:
            raise ValueError(f"Variable {variable.name} is not randc")
        
        var_name = variable.name
        
        # Check if we need to reset due to constraint changes
        if var_name in self.state:
            _, _, old_version = self.state[var_name]
            if old_version != constraint_version:
                # Constraints changed, reset
                self._reset_variable(var_name)
        
        # Check if we need a new permutation
        if var_name not in self.state:
            # Generate new permutation from available domain
            values = list(available_domain.values())
            if not values:
                # No values available
                return None
            
            permutation = self._generate_permutation(values)
            self.state[var_name] = (permutation, 0, constraint_version)
            self.retry_counts[var_name] = 0
        
        # Get current state
        permutation, position, _ = self.state[var_name]
        
        # Check if we've exhausted the current permutation
        if position >= len(permutation):
            # Try generating a new permutation
            self.retry_counts[var_name] += 1
            
            if self.retry_counts[var_name] >= self.config.max_permutation_retries:
                # Exhausted retries, give up
                return None
            
            # Generate new permutation
            values = list(available_domain.values())
            if not values:
                return None
            
            permutation = self._generate_permutation(values)
            self.state[var_name] = (permutation, 0, constraint_version)
            position = 0
        
        # Return next value and advance position
        value = permutation[position]
        self.state[var_name] = (permutation, position + 1, constraint_version)
        
        return value
    
    def mark_value_failed(self, variable: Variable):
        """
        Mark that the last value failed (conflict).
        This is a no-op since we automatically try the next value.
        
        Args:
            variable: The randc variable
        """
        # Position was already advanced in get_next_value
        # The retry loop will automatically try the next value
        pass
    
    def mark_value_success(self, variable: Variable, value: int):
        """
        Mark that a value was successfully used.
        Records it in the variable's randc_state.
        
        Args:
            variable: The randc variable
            value: The value that was successfully assigned
        """
        if variable.randc_state is not None:
            variable.randc_state.mark_used(value)
            
            # Check if cycle complete
            if variable.randc_state.cycle_complete:
                # Reset for next cycle
                variable.randc_state.reset_cycle()
                self._reset_variable(variable.name)
    
    def reset_on_constraint_change(self, constraint_version: int):
        """
        Reset all randc state due to constraint changes.
        
        Args:
            constraint_version: New constraint version number
        """
        self.config.constraint_version = constraint_version
        self.state.clear()
        self.retry_counts.clear()
    
    def _generate_permutation(self, values: List[int]) -> List[int]:
        """
        Generate a random permutation of values.
        
        Args:
            values: List of values to permute
            
        Returns:
            Shuffled list of values
        """
        permutation = list(values)
        self.rng.shuffle(permutation)
        return permutation
    
    def _reset_variable(self, var_name: str):
        """Reset state for a specific variable"""
        if var_name in self.state:
            del self.state[var_name]
        if var_name in self.retry_counts:
            del self.retry_counts[var_name]
    
    def get_available_values(self, variable: Variable) -> Set[int]:
        """
        Get set of values still available in current cycle.
        
        Args:
            variable: The randc variable
            
        Returns:
            Set of available values (not yet used in cycle)
        """
        if variable.randc_state is None:
            # Not a randc variable, return all domain values
            return set(variable.domain.values())
        
        # Get values not yet used
        all_values = set(variable.domain.values())
        used_values = set(variable.randc_state.used_values)
        return all_values - used_values
    
    def get_retry_count(self, variable: Variable) -> int:
        """
        Get number of permutation retries for a variable.
        
        Args:
            variable: The randc variable
            
        Returns:
            Number of permutation retries attempted
        """
        return self.retry_counts.get(variable.name, 0)
