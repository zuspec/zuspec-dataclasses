"""Range analysis pass with interval arithmetic for bit-vectors."""

from typing import Dict, Tuple, Optional
from ..core.variable import Variable
from ..core.domain import IntDomain


class RangeAnalyzer:
    """
    Performs interval-based range analysis on constraints.
    Uses modular arithmetic for bit-vector operations.
    """
    
    def __init__(self, bit_width: int = 64):
        self.bit_width = bit_width
        self.modulo = 2 ** bit_width
        self.ranges: Dict[str, Tuple[int, int]] = {}
    
    def analyze(self, variables: Dict[str, Variable]) -> Dict[str, Tuple[int, int]]:
        """
        Compute min/max bounds for all variables from their domains.
        Returns dict of variable_name -> (min, max).
        """
        # Initialize ranges from variable domains
        for var_name, var in variables.items():
            if var.domain and not var.domain.is_empty():
                # Get min from first interval, max from last interval
                intervals = var.domain.intervals
                self.ranges[var_name] = (intervals[0][0], intervals[-1][1])
            else:
                # Default to full bit-vector range
                self.ranges[var_name] = (0, self.modulo - 1)
        
        # TODO: Iteratively refine ranges by analyzing constraints
        # This requires expression tree traversal
        
        return self.ranges.copy()
    
    def prune_domains(self, variables: Dict[str, Variable]) -> Dict[str, bool]:
        """
        Prune variable domains based on computed ranges.
        Returns dict of variable_name -> domain_changed.
        """
        changed = {}
        for var_name, var in variables.items():
            if var_name in self.ranges and var.domain:
                min_val, max_val = self.ranges[var_name]
                
                # Get current domain bounds
                intervals = var.domain.intervals
                if intervals:
                    old_min = intervals[0][0]
                    old_max = intervals[-1][1]
                    
                    # Intersect with computed range
                    new_min = max(old_min, min_val)
                    new_max = min(old_max, max_val)
                    
                    if new_min != old_min or new_max != old_max:
                        # Create new domain with restricted range
                        var.domain = IntDomain([(new_min, new_max)], var.domain.width, var.domain.signed)
                        changed[var_name] = True
        return changed
    
    def detect_unsat(self) -> bool:
        """Check if any domain became empty."""
        for var_name, (min_val, max_val) in self.ranges.items():
            if min_val > max_val:
                return True
        return False
