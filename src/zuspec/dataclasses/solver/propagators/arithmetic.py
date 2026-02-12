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
        """Compute intervals for result - subtrahend with wrapping."""
        diff_intervals = []
        
        for res_lo, res_hi in result_intervals:
            for sub_lo, sub_hi in subtrahend_intervals:
                # Compute min and max differences
                min_diff = (res_lo - sub_hi) % self.modulo
                max_diff = (res_hi - sub_lo) % self.modulo
                
                # Check if wrapping occurred
                if res_lo - sub_hi < 0 or res_hi - sub_lo < 0:
                    # Wrapping - conservative
                    diff_intervals.append((0, self.modulo - 1))
                else:
                    diff_intervals.append((min_diff, max_diff))
        
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
        
        # Forward propagation: result = lhs - rhs
        result_intervals = []
        for lhs_lo, lhs_hi in lhs.domain.intervals:
            for rhs_lo, rhs_hi in rhs.domain.intervals:
                min_diff = (lhs_lo - rhs_hi) % self.modulo
                max_diff = (lhs_hi - rhs_lo) % self.modulo
                
                if lhs_lo - rhs_hi < 0 or lhs_hi - rhs_lo < 0:
                    result_intervals.append((0, self.modulo - 1))
                else:
                    result_intervals.append((min_diff, max_diff))
        
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
                min_diff = (lhs_lo - res_hi) % self.modulo
                max_diff = (lhs_hi - res_lo) % self.modulo
                
                if lhs_lo - res_hi < 0 or lhs_hi - res_lo < 0:
                    rhs_intervals.append((0, self.modulo - 1))
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
        """Forward propagation for multiplication."""
        result = variables.get(self.result_var)
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([result, lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if any(v.domain.is_empty() for v in [result, lhs, rhs]):
            return PropagationResult.conflict()
        
        changed = set()
        
        # Check if domains are small enough to enumerate
        if lhs.domain.size() * rhs.domain.size() <= self.small_domain_threshold:
            # Exact enumeration
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
        """Forward propagation for division."""
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
        
        # Forward propagation with conservative bounds
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
        """Forward propagation for modulo."""
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
        
        # Constrain result: 0 <= result < |rhs|
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
