"""Arithmetic propagators with bit-vector wrapping support."""

from typing import Dict, Set, Tuple, List
from ..core.variable import Variable
from ..core.domain import IntDomain
from .base import Propagator, PropagationResult, PropagationStatus


class AddPropagator(Propagator):
    """
    Propagator for addition: result = lhs + rhs
    
    Handles bit-vector wrapping for modular arithmetic.
    """
    
    def __init__(self, result_var: str, lhs_var: str, rhs_var: str, bit_width: int = 64):
        self.result_var = result_var
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
        self.bit_width = bit_width
        self.modulo = 2 ** bit_width
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Forward and backward propagation for addition."""
        result = variables.get(self.result_var)
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([result, lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if any(v.domain.is_empty() for v in [result, lhs, rhs]):
            return PropagationResult.conflict()
        
        changed = set()
        
        # For small domains, use precise enumeration
        small_threshold = 1000
        same_var = (self.lhs_var == self.rhs_var)
        if lhs.domain.size() * rhs.domain.size() <= small_threshold:
            # Precise forward propagation
            valid_sums = set()
            if same_var:
                # lhs and rhs are the same variable: result = 2 * lhs
                for val in lhs.domain.values():
                    valid_sums.add((2 * val) % self.modulo)
            else:
                for lhs_val in lhs.domain.values():
                    for rhs_val in rhs.domain.values():
                        valid_sums.add((lhs_val + rhs_val) % self.modulo)
            
            # Constrain result
            result_intervals = self._values_to_intervals(valid_sums)
            new_result = IntDomain(result_intervals, result.domain.width, result.domain.signed)
            old_result = result.domain
            result.domain = result.domain.intersect(new_result)
            
            if result.domain.is_empty():
                return PropagationResult.conflict()
            if result.domain != old_result:
                changed.add(result)
            
            # Precise backward propagation
            result_values = set(result.domain.values())
            valid_lhs = set()
            valid_rhs = set()
            
            if same_var:
                # result = 2 * lhs, so lhs = result / 2 (only even sums are valid)
                lhs_vals = set(lhs.domain.values())
                for sum_val in result_values:
                    if sum_val % 2 == 0:
                        half = sum_val // 2
                        if half in lhs_vals:
                            valid_lhs.add(half)
                valid_rhs = valid_lhs
            else:
                for lhs_val in lhs.domain.values():
                    for rhs_val in rhs.domain.values():
                        if (lhs_val + rhs_val) % self.modulo in result_values:
                            valid_lhs.add(lhs_val)
                            valid_rhs.add(rhs_val)
            
            # Constrain lhs
            if valid_lhs:
                lhs_intervals = self._values_to_intervals(valid_lhs)
                new_lhs = IntDomain(lhs_intervals, lhs.domain.width, lhs.domain.signed)
                old_lhs = lhs.domain
                lhs.domain = lhs.domain.intersect(new_lhs)
                
                if lhs.domain.is_empty():
                    return PropagationResult.conflict()
                if lhs.domain != old_lhs:
                    changed.add(lhs)
            else:
                lhs.domain = IntDomain([], lhs.domain.width, lhs.domain.signed)
                return PropagationResult.conflict()
            
            # Constrain rhs
            if valid_rhs:
                rhs_intervals = self._values_to_intervals(valid_rhs)
                new_rhs = IntDomain(rhs_intervals, rhs.domain.width, rhs.domain.signed)
                old_rhs = rhs.domain
                rhs.domain = rhs.domain.intersect(new_rhs)
                
                if rhs.domain.is_empty():
                    return PropagationResult.conflict()
                if rhs.domain != old_rhs:
                    changed.add(rhs)
            else:
                rhs.domain = IntDomain([], rhs.domain.width, rhs.domain.signed)
                return PropagationResult.conflict()
        else:
            # Conservative interval arithmetic for large domains
            # Forward propagation: constrain result based on lhs + rhs
            result_intervals = self._compute_sum_intervals(
                lhs.domain.intervals, rhs.domain.intervals
            )
            new_result_domain = IntDomain(result_intervals, result.domain.width, result.domain.signed)
            old_result = result.domain
            result.domain = result.domain.intersect(new_result_domain)
            
            if result.domain.is_empty():
                return PropagationResult.conflict()
            if result.domain != old_result:
                changed.add(result)
            
            # Backward propagation: constrain lhs based on result - rhs
            lhs_intervals = self._compute_diff_intervals(
                result.domain.intervals, rhs.domain.intervals
            )
            new_lhs_domain = IntDomain(lhs_intervals, lhs.domain.width, lhs.domain.signed)
            old_lhs = lhs.domain
            lhs.domain = lhs.domain.intersect(new_lhs_domain)
            
            if lhs.domain.is_empty():
                return PropagationResult.conflict()
            if lhs.domain != old_lhs:
                changed.add(lhs)
            
            # Backward propagation: constrain rhs based on result - lhs
            rhs_intervals = self._compute_diff_intervals(
                result.domain.intervals, lhs.domain.intervals
            )
            new_rhs_domain = IntDomain(rhs_intervals, rhs.domain.width, rhs.domain.signed)
            old_rhs = rhs.domain
            rhs.domain = rhs.domain.intersect(new_rhs_domain)
            
            if rhs.domain.is_empty():
                return PropagationResult.conflict()
            if rhs.domain != old_rhs:
                changed.add(rhs)
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def _values_to_intervals(self, values: Set[int]) -> List[Tuple[int, int]]:
        """Convert a set of values to a list of intervals"""
        if not values:
            return []
        
        sorted_vals = sorted(values)
        intervals = []
        start = sorted_vals[0]
        end = start
        
        for val in sorted_vals[1:]:
            if val == end + 1:
                end = val
            else:
                intervals.append((start, end))
                start = val
                end = val
        intervals.append((start, end))
        return intervals
    
    def _compute_sum_intervals(
        self, lhs_intervals: List[Tuple[int, int]], rhs_intervals: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Compute intervals for lhs + rhs with wrapping."""
        result_intervals = []
        
        for lhs_lo, lhs_hi in lhs_intervals:
            for rhs_lo, rhs_hi in rhs_intervals:
                # Compute min and max sums
                min_sum = (lhs_lo + rhs_lo) % self.modulo
                max_sum = (lhs_hi + rhs_hi) % self.modulo
                
                # Check if wrapping occurred
                if lhs_lo + rhs_lo >= self.modulo or lhs_hi + rhs_hi >= self.modulo:
                    # Wrapping - may need to split into multiple intervals
                    # Conservative: full range
                    result_intervals.append((0, self.modulo - 1))
                else:
                    result_intervals.append((min_sum, max_sum))
        
        return result_intervals
    
    def _compute_diff_intervals(
        self, result_intervals: List[Tuple[int, int]], subtrahend_intervals: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Compute intervals for result - subtrahend (backward propagation for addition).

        For each combination of result interval [r_lo, r_hi] and subtrahend interval
        [s_lo, s_hi], the difference d = result - subtrahend ranges in
        [r_lo - s_hi, r_hi - s_lo].  Three cases:

        * all non-negative  (d_lo >= 0): single interval [d_lo, d_hi]
        * mixed sign        (d_lo < 0 <= d_hi): non-wrapping part [0, d_hi]  PLUS
                                                 wrapping part  [modulo+d_lo, modulo-1]
        * all negative      (d_hi < 0): pure wrap-around [modulo+d_lo, modulo+d_hi]
        """
        diff_intervals = []

        for res_lo, res_hi in result_intervals:
            for sub_lo, sub_hi in subtrahend_intervals:
                d_lo = res_lo - sub_hi   # minimum possible difference
                d_hi = res_hi - sub_lo   # maximum possible difference

                if d_hi < 0:
                    # All differences are negative – only wrap-around values exist.
                    diff_intervals.append((self.modulo + d_lo, self.modulo + d_hi))
                elif d_lo < 0:
                    # Partial: non-wrapping part [0, d_hi] plus wrapping part.
                    diff_intervals.append((0, d_hi))
                    diff_intervals.append((self.modulo + d_lo, self.modulo - 1))
                else:
                    diff_intervals.append((d_lo, d_hi))

        return diff_intervals
    
    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.result_var, self.lhs_var, self.rhs_var]):
            return False
        expected = (assignment[self.lhs_var] + assignment[self.rhs_var]) % self.modulo
        return assignment[self.result_var] == expected


class SubPropagator(Propagator):
    """
    Propagator for subtraction: result = lhs - rhs
    
    Handles bit-vector wrapping for modular arithmetic.
    """
    
    def __init__(self, result_var: str, lhs_var: str, rhs_var: str, bit_width: int = 64):
        self.result_var = result_var
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
        self.bit_width = bit_width
        self.modulo = 2 ** bit_width
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Forward and backward propagation for subtraction."""
        result = variables.get(self.result_var)
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([result, lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if any(v.domain.is_empty() for v in [result, lhs, rhs]):
            return PropagationResult.conflict()
        
        changed = set()
        
        # For small domains, use precise enumeration
        small_threshold = 1000
        if lhs.domain.size() * rhs.domain.size() <= small_threshold:
            # Precise forward propagation
            valid_diffs = set()
            for lhs_val in lhs.domain.values():
                for rhs_val in rhs.domain.values():
                    valid_diffs.add((lhs_val - rhs_val) % self.modulo)
            
            # Constrain result
            result_intervals = self._values_to_intervals(valid_diffs)
            new_result = IntDomain(result_intervals, result.domain.width, result.domain.signed)
            old_result = result.domain
            result.domain = result.domain.intersect(new_result)
            
            if result.domain.is_empty():
                return PropagationResult.conflict()
            if result.domain != old_result:
                changed.add(result)
            
            # Precise backward propagation
            result_values = set(result.domain.values())
            valid_lhs = set()
            valid_rhs = set()
            
            for lhs_val in lhs.domain.values():
                for rhs_val in rhs.domain.values():
                    if (lhs_val - rhs_val) % self.modulo in result_values:
                        valid_lhs.add(lhs_val)
                        valid_rhs.add(rhs_val)
            
            # Constrain lhs
            if valid_lhs:
                lhs_intervals = self._values_to_intervals(valid_lhs)
                new_lhs = IntDomain(lhs_intervals, lhs.domain.width, lhs.domain.signed)
                old_lhs = lhs.domain
                lhs.domain = lhs.domain.intersect(new_lhs)
                
                if lhs.domain.is_empty():
                    return PropagationResult.conflict()
                if lhs.domain != old_lhs:
                    changed.add(lhs)
            else:
                lhs.domain = IntDomain([], lhs.domain.width, lhs.domain.signed)
                return PropagationResult.conflict()
            
            # Constrain rhs
            if valid_rhs:
                rhs_intervals = self._values_to_intervals(valid_rhs)
                new_rhs = IntDomain(rhs_intervals, rhs.domain.width, rhs.domain.signed)
                old_rhs = rhs.domain
                rhs.domain = rhs.domain.intersect(new_rhs)
                
                if rhs.domain.is_empty():
                    return PropagationResult.conflict()
                if rhs.domain != old_rhs:
                    changed.add(rhs)
            else:
                rhs.domain = IntDomain([], rhs.domain.width, rhs.domain.signed)
                return PropagationResult.conflict()
        else:
            # Conservative interval arithmetic for large domains
            # Forward propagation: result = lhs - rhs
            result_intervals = []
            for lhs_lo, lhs_hi in lhs.domain.intervals:
                for rhs_lo, rhs_hi in rhs.domain.intervals:
                    d_lo = lhs_lo - rhs_hi
                    d_hi = lhs_hi - rhs_lo
                    if d_hi < 0:
                        result_intervals.append((self.modulo + d_lo, self.modulo + d_hi))
                    elif d_lo < 0:
                        result_intervals.append((0, d_hi))
                        result_intervals.append((self.modulo + d_lo, self.modulo - 1))
                    else:
                        result_intervals.append((d_lo, d_hi))
            
            new_result = IntDomain(result_intervals, result.domain.width, result.domain.signed)
            old_result = result.domain
            result.domain = result.domain.intersect(new_result)
            
            if result.domain.is_empty():
                return PropagationResult.conflict()
            if result.domain != old_result:
                changed.add(result)
            
            # Backward: lhs = result + rhs
            lhs_intervals = []
            for res_lo, res_hi in result.domain.intervals:
                for rhs_lo, rhs_hi in rhs.domain.intervals:
                    min_sum = (res_lo + rhs_lo) % self.modulo
                    max_sum = (res_hi + rhs_hi) % self.modulo
                    
                    if res_lo + rhs_lo >= self.modulo or res_hi + rhs_hi >= self.modulo:
                        lhs_intervals.append((0, self.modulo - 1))
                    else:
                        lhs_intervals.append((min_sum, max_sum))
            
            new_lhs = IntDomain(lhs_intervals, lhs.domain.width, lhs.domain.signed)
            old_lhs = lhs.domain
            lhs.domain = lhs.domain.intersect(new_lhs)
            
            if lhs.domain.is_empty():
                return PropagationResult.conflict()
            if lhs.domain != old_lhs:
                changed.add(lhs)
            
            # Backward: rhs = lhs - result
            rhs_intervals = []
            for lhs_lo, lhs_hi in lhs.domain.intervals:
                for res_lo, res_hi in result.domain.intervals:
                    d_lo = lhs_lo - res_hi
                    d_hi = lhs_hi - res_lo
                    if d_hi < 0:
                        rhs_intervals.append((self.modulo + d_lo, self.modulo + d_hi))
                    elif d_lo < 0:
                        rhs_intervals.append((0, d_hi))
                        rhs_intervals.append((self.modulo + d_lo, self.modulo - 1))
                    else:
                        rhs_intervals.append((min_diff, max_diff))
        
        new_rhs = IntDomain(rhs_intervals, rhs.domain.width, rhs.domain.signed)
        old_rhs = rhs.domain
        rhs.domain = rhs.domain.intersect(new_rhs)
        
        if rhs.domain.is_empty():
            return PropagationResult.conflict()
        if rhs.domain != old_rhs:
            changed.add(rhs)
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def _values_to_intervals(self, values: Set[int]) -> List[Tuple[int, int]]:
        """Convert a set of values to a list of intervals"""
        if not values:
            return []
        
        sorted_vals = sorted(values)
        intervals = []
        start = sorted_vals[0]
        end = start
        
        for val in sorted_vals[1:]:
            if val == end + 1:
                end = val
            else:
                intervals.append((start, end))
                start = val
                end = val
        intervals.append((start, end))
        return intervals
    
    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.result_var, self.lhs_var, self.rhs_var]):
            return False
        expected = (assignment[self.lhs_var] - assignment[self.rhs_var]) % self.modulo
        return assignment[self.result_var] == expected


class MultPropagator(Propagator):
    """
    Propagator for multiplication: result = lhs * rhs
    
    Handles non-convex domains by enumerating for small domains
    and using conservative bounds for large domains.
    """
    
    def __init__(self, result_var: str, lhs_var: str, rhs_var: str, 
                 bit_width: int = 64, small_domain_threshold: int = 1000):
        self.result_var = result_var
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
        self.bit_width = bit_width
        self.modulo = 2 ** bit_width
        self.small_domain_threshold = small_domain_threshold
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Forward and backward propagation for multiplication."""
        result = variables.get(self.result_var)
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([result, lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if any(v.domain.is_empty() for v in [result, lhs, rhs]):
            return PropagationResult.conflict()
        
        changed = set()
        
        # Forward propagation: constrain result based on lhs * rhs
        # Check if domains are small enough to enumerate
        if lhs.domain.size() * rhs.domain.size() <= self.small_domain_threshold:
            # Exact enumeration for forward propagation
            products = set()
            for lhs_val in lhs.domain.values():
                for rhs_val in rhs.domain.values():
                    products.add((lhs_val * rhs_val) % self.modulo)
            
            # Convert to intervals
            if products:
                sorted_products = sorted(products)
                result_intervals = []
                start = sorted_products[0]
                end = start
                
                for val in sorted_products[1:]:
                    if val == end + 1:
                        end = val
                    else:
                        result_intervals.append((start, end))
                        start = val
                        end = val
                result_intervals.append((start, end))
                
                new_result = IntDomain(result_intervals, result.domain.width, result.domain.signed)
                old_result = result.domain
                result.domain = result.domain.intersect(new_result)
                
                if result.domain.is_empty():
                    return PropagationResult.conflict()
                if result.domain != old_result:
                    changed.add(result)
        else:
            # Conservative bounds propagation
            result_intervals = []
            for lhs_lo, lhs_hi in lhs.domain.intervals:
                for rhs_lo, rhs_hi in rhs.domain.intervals:
                    products = [
                        (lhs_lo * rhs_lo) % self.modulo,
                        (lhs_lo * rhs_hi) % self.modulo,
                        (lhs_hi * rhs_lo) % self.modulo,
                        (lhs_hi * rhs_hi) % self.modulo,
                    ]
                    result_intervals.append((min(products), max(products)))
            
            new_result = IntDomain(result_intervals, result.domain.width, result.domain.signed)
            old_result = result.domain
            result.domain = result.domain.intersect(new_result)
            
            if result.domain.is_empty():
                return PropagationResult.conflict()
            if result.domain != old_result:
                changed.add(result)
        
        # Backward propagation: constrain lhs and rhs based on result
        # Only do this for small domains to avoid performance issues
        if (lhs.domain.size() * rhs.domain.size() <= self.small_domain_threshold and 
            result.domain.size() <= 100):
            # Enumerate valid (lhs, rhs) pairs
            valid_lhs = set()
            valid_rhs = set()
            
            # Get result values as a set for fast membership checking
            result_values = set(result.domain.values())
            
            for lhs_val in lhs.domain.values():
                for rhs_val in rhs.domain.values():
                    product = (lhs_val * rhs_val) % self.modulo
                    if product in result_values:
                        valid_lhs.add(lhs_val)
                        valid_rhs.add(rhs_val)
            
            # Update lhs domain
            if valid_lhs:
                sorted_lhs = sorted(valid_lhs)
                lhs_intervals = []
                start = sorted_lhs[0]
                end = start
                
                for val in sorted_lhs[1:]:
                    if val == end + 1:
                        end = val
                    else:
                        lhs_intervals.append((start, end))
                        start = val
                        end = val
                lhs_intervals.append((start, end))
                
                new_lhs = IntDomain(lhs_intervals, lhs.domain.width, lhs.domain.signed)
                old_lhs = lhs.domain
                lhs.domain = lhs.domain.intersect(new_lhs)
                
                if lhs.domain.is_empty():
                    return PropagationResult.conflict()
                if lhs.domain != old_lhs:
                    changed.add(lhs)
            else:
                # No valid lhs values
                lhs.domain = IntDomain([], lhs.domain.width, lhs.domain.signed)
                return PropagationResult.conflict()
            
            # Update rhs domain
            if valid_rhs:
                sorted_rhs = sorted(valid_rhs)
                rhs_intervals = []
                start = sorted_rhs[0]
                end = start
                
                for val in sorted_rhs[1:]:
                    if val == end + 1:
                        end = val
                    else:
                        rhs_intervals.append((start, end))
                        start = val
                        end = val
                rhs_intervals.append((start, end))
                
                new_rhs = IntDomain(rhs_intervals, rhs.domain.width, rhs.domain.signed)
                old_rhs = rhs.domain
                rhs.domain = rhs.domain.intersect(new_rhs)
                
                if rhs.domain.is_empty():
                    return PropagationResult.conflict()
                if rhs.domain != old_rhs:
                    changed.add(rhs)
            else:
                # No valid rhs values
                rhs.domain = IntDomain([], rhs.domain.width, rhs.domain.signed)
                return PropagationResult.conflict()
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.result_var, self.lhs_var, self.rhs_var]):
            return False
        expected = (assignment[self.lhs_var] * assignment[self.rhs_var]) % self.modulo
        return assignment[self.result_var] == expected


class DivPropagator(Propagator):
    """
    Propagator for division: result = lhs / rhs
    
    Enforces rhs != 0 constraint.
    """
    
    def __init__(self, result_var: str, lhs_var: str, rhs_var: str):
        self.result_var = result_var
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Forward and backward propagation for division."""
        result = variables.get(self.result_var)
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([result, lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if any(v.domain.is_empty() for v in [result, lhs, rhs]):
            return PropagationResult.conflict()
        
        changed = set()
        
        # Ensure rhs != 0
        old_rhs = rhs.domain
        if rhs.domain.remove_value(0):
            changed.add(rhs)
        
        if rhs.domain.is_empty():
            return PropagationResult.conflict()
        
        # For small domains, use precise enumeration
        small_threshold = 1000
        if lhs.domain.size() * rhs.domain.size() <= small_threshold:
            # Precise forward and backward propagation via enumeration
            valid_quotients = set()
            valid_lhs = set()
            valid_rhs = set()
            
            # Get result values as a set for fast membership checking
            result_values = set(result.domain.values())
            
            for lhs_val in lhs.domain.values():
                for rhs_val in rhs.domain.values():
                    if rhs_val == 0:
                        continue
                    quotient = lhs_val // rhs_val
                    valid_quotients.add(quotient)
                    
                    # Check if this combination produces a valid result
                    if quotient in result_values:
                        valid_lhs.add(lhs_val)
                        valid_rhs.add(rhs_val)
            
            # Constrain result
            if valid_quotients:
                result_intervals = self._values_to_intervals(valid_quotients)
                new_result = IntDomain(result_intervals, result.domain.width, result.domain.signed)
                old_result = result.domain
                result.domain = result.domain.intersect(new_result)
                
                if result.domain.is_empty():
                    return PropagationResult.conflict()
                if result.domain != old_result:
                    changed.add(result)
            
            # Constrain lhs (backward propagation)
            if valid_lhs:
                lhs_intervals = self._values_to_intervals(valid_lhs)
                new_lhs = IntDomain(lhs_intervals, lhs.domain.width, lhs.domain.signed)
                old_lhs = lhs.domain
                lhs.domain = lhs.domain.intersect(new_lhs)
                
                if lhs.domain.is_empty():
                    return PropagationResult.conflict()
                if lhs.domain != old_lhs:
                    changed.add(lhs)
            else:
                lhs.domain = IntDomain([], lhs.domain.width, lhs.domain.signed)
                return PropagationResult.conflict()
            
            # Constrain rhs (backward propagation)
            if valid_rhs:
                rhs_intervals = self._values_to_intervals(valid_rhs)
                new_rhs = IntDomain(rhs_intervals, rhs.domain.width, rhs.domain.signed)
                old_rhs = rhs.domain
                rhs.domain = rhs.domain.intersect(new_rhs)
                
                if rhs.domain.is_empty():
                    return PropagationResult.conflict()
                if rhs.domain != old_rhs:
                    changed.add(rhs)
            else:
                rhs.domain = IntDomain([], rhs.domain.width, rhs.domain.signed)
                return PropagationResult.conflict()
        else:
            # Conservative bounds propagation for large domains
            result_intervals = []
            for lhs_lo, lhs_hi in lhs.domain.intervals:
                for rhs_lo, rhs_hi in rhs.domain.intervals:
                    if rhs_lo <= 0 <= rhs_hi:
                        # Skip intervals containing zero
                        continue
                    
                    quotients = []
                    if rhs_lo != 0:
                        quotients.extend([lhs_lo // rhs_lo, lhs_hi // rhs_lo])
                    if rhs_hi != 0:
                        quotients.extend([lhs_lo // rhs_hi, lhs_hi // rhs_hi])
                    
                    if quotients:
                        result_intervals.append((min(quotients), max(quotients)))
            
            if result_intervals:
                new_result = IntDomain(result_intervals, result.domain.width, result.domain.signed)
                old_result = result.domain
                result.domain = result.domain.intersect(new_result)
                
                if result.domain.is_empty():
                    return PropagationResult.conflict()
                if result.domain != old_result:
                    changed.add(result)
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def _values_to_intervals(self, values: Set[int]) -> List[Tuple[int, int]]:
        """Convert a set of values to a list of intervals"""
        if not values:
            return []
        
        sorted_vals = sorted(values)
        intervals = []
        start = sorted_vals[0]
        end = start
        
        for val in sorted_vals[1:]:
            if val == end + 1:
                end = val
            else:
                intervals.append((start, end))
                start = val
                end = val
        intervals.append((start, end))
        return intervals
    
    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.result_var, self.lhs_var, self.rhs_var]):
            return False
        if assignment[self.rhs_var] == 0:
            return False
        expected = assignment[self.lhs_var] // assignment[self.rhs_var]
        return assignment[self.result_var] == expected


class ModPropagator(Propagator):
    """
    Propagator for modulo: result = lhs % rhs
    
    Enforces rhs != 0 constraint.
    """
    
    def __init__(self, result_var: str, lhs_var: str, rhs_var: str):
        self.result_var = result_var
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Forward and backward propagation for modulo."""
        result = variables.get(self.result_var)
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([result, lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if any(v.domain.is_empty() for v in [result, lhs, rhs]):
            return PropagationResult.conflict()
        
        changed = set()
        
        # Ensure rhs != 0
        old_rhs = rhs.domain
        if rhs.domain.remove_value(0):
            changed.add(rhs)
        
        if rhs.domain.is_empty():
            return PropagationResult.conflict()
        
        # Forward propagation: constrain result: 0 <= result < |rhs|
        result_intervals = []
        for rhs_lo, rhs_hi in rhs.domain.intervals:
            if rhs_lo <= 0 <= rhs_hi:
                continue
            max_mod = max(abs(rhs_lo), abs(rhs_hi)) - 1
            result_intervals.append((0, max_mod))
        
        if result_intervals:
            new_result = IntDomain(result_intervals, result.domain.width, result.domain.signed)
            old_result = result.domain
            result.domain = result.domain.intersect(new_result)
            
            if result.domain.is_empty():
                return PropagationResult.conflict()
            if result.domain != old_result:
                changed.add(result)
        
        # Backward propagation: constrain lhs based on result and rhs
        # For lhs % rhs == result, lhs must be in the set of values where lhs % rhs ∈ result.domain
        # When rhs and result are both small/constrained, filter lhs
        if rhs.domain.size() <= 10 and result.domain.size() <= 10:
            # Enumerate valid lhs values
            valid_result_values = set(result.domain.values())
            valid_lhs_values = []
            for lhs_val in lhs.domain.values():
                for rhs_val in rhs.domain.values():
                    if rhs_val == 0:
                        continue
                    mod_result = lhs_val % rhs_val
                    if mod_result in valid_result_values:
                        valid_lhs_values.append(lhs_val)
                        break  # This lhs value is valid
            
            if valid_lhs_values:
                # Create new domain from valid values
                if valid_lhs_values:
                    valid_lhs_values = sorted(set(valid_lhs_values))
                    new_lhs_intervals = []
                    # Group consecutive values into intervals
                    start = valid_lhs_values[0]
                    end = valid_lhs_values[0]
                    for val in valid_lhs_values[1:]:
                        if val == end + 1:
                            end = val
                        else:
                            new_lhs_intervals.append((start, end))
                            start = val
                            end = val
                    new_lhs_intervals.append((start, end))
                    
                    new_lhs_domain = IntDomain(new_lhs_intervals, lhs.domain.width, lhs.domain.signed)
                    old_lhs = lhs.domain
                    lhs.domain = lhs.domain.intersect(new_lhs_domain)
                    
                    if lhs.domain.is_empty():
                        return PropagationResult.conflict()
                    if lhs.domain != old_lhs:
                        changed.add(lhs)
            else:
                # No valid lhs values
                return PropagationResult.conflict()
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.result_var, self.lhs_var, self.rhs_var]):
            return False
        if assignment[self.rhs_var] == 0:
            return False
        expected = assignment[self.lhs_var] % assignment[self.rhs_var]
        return assignment[self.result_var] == expected


class EqualSumPropagator(Propagator):
    """Fused propagator: result_var == lhs_var + rhs_var.

    Combines AddPropagator + EqualPropagator into a single propagator
    that directly enforces the equality without a temporary variable.
    Uses interval arithmetic for large domains.
    """

    def __init__(self, result_var: str, lhs_var: str, rhs_var: str, bit_width: int = 64):
        self.result_var = result_var
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
        self.bit_width = bit_width
        self.modulo = 2 ** bit_width

    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        result = variables.get(self.result_var)
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)

        if not all([result, lhs, rhs]):
            return PropagationResult.fixed_point()
        if any(v.domain.is_empty() for v in [result, lhs, rhs]):
            return PropagationResult.conflict()

        changed = set()

        # Forward: result must be within lhs + rhs range
        for lhs_iv in lhs.domain.intervals:
            for rhs_iv in rhs.domain.intervals:
                pass  # just checking non-empty
        fwd = self._sum_intervals(lhs.domain.intervals, rhs.domain.intervals)
        new_r = IntDomain(fwd, result.domain.width, result.domain.signed)
        old_r = result.domain
        result.domain = result.domain.intersect(new_r)
        if result.domain.is_empty():
            return PropagationResult.conflict()
        if result.domain != old_r:
            changed.add(result)

        # Backward: lhs must be within result - rhs range
        bwd_l = self._diff_intervals(result.domain.intervals, rhs.domain.intervals)
        new_l = IntDomain(bwd_l, lhs.domain.width, lhs.domain.signed)
        old_l = lhs.domain
        lhs.domain = lhs.domain.intersect(new_l)
        if lhs.domain.is_empty():
            return PropagationResult.conflict()
        if lhs.domain != old_l:
            changed.add(lhs)

        # Backward: rhs must be within result - lhs range
        bwd_r = self._diff_intervals(result.domain.intervals, lhs.domain.intervals)
        new_rr = IntDomain(bwd_r, rhs.domain.width, rhs.domain.signed)
        old_rr = rhs.domain
        rhs.domain = rhs.domain.intersect(new_rr)
        if rhs.domain.is_empty():
            return PropagationResult.conflict()
        if rhs.domain != old_rr:
            changed.add(rhs)

        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()

    def _sum_intervals(self, a_ivs, b_ivs):
        result = []
        for a_lo, a_hi in a_ivs:
            for b_lo, b_hi in b_ivs:
                s_lo = a_lo + b_lo
                s_hi = a_hi + b_hi
                if s_lo >= self.modulo or s_hi >= self.modulo:
                    result.append((0, self.modulo - 1))
                else:
                    result.append((s_lo, s_hi))
        return result

    def _diff_intervals(self, res_ivs, sub_ivs):
        result = []
        for r_lo, r_hi in res_ivs:
            for s_lo, s_hi in sub_ivs:
                d_lo = r_lo - s_hi
                d_hi = r_hi - s_lo
                if d_hi < 0:
                    result.append((self.modulo + d_lo, self.modulo + d_hi))
                elif d_lo < 0:
                    result.append((0, d_hi))
                    result.append((self.modulo + d_lo, self.modulo - 1))
                else:
                    result.append((d_lo, d_hi))
        return result

    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.lhs_var, self.rhs_var}

    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.result_var, self.lhs_var, self.rhs_var]):
            return False
        return assignment[self.result_var] == (assignment[self.lhs_var] + assignment[self.rhs_var]) % self.modulo
