"""
Reification propagators - link boolean variables to constraint truth values.

Reification allows constraints to produce boolean result variables that represent
whether the constraint is satisfied. This is essential for implications and
other meta-constraints.

Example:
    result_var = reified(x > 5)
    
    When x=10: result_var must be 1 (true)
    When x=3: result_var must be 0 (false)
    When result_var=1: x must be > 5
    When result_var=0: x must be <= 5
"""

from typing import Dict, Set
from ..core.variable import Variable
from ..core.domain import IntDomain
from .base import Propagator, PropagationResult
from zuspec.dataclasses.ir.expr import CmpOp


class ComparisonReifier(Propagator):
    """
    Reifies a comparison into a boolean variable.
    
    Enforces: bool_var ↔ (lhs op rhs)
    
    Where bool_var ∈ {0, 1}:
    - bool_var = 1 means the comparison is true
    - bool_var = 0 means the comparison is false
    
    Bidirectional propagation:
    1. If comparison becomes definitely true → bool_var = 1
    2. If comparison becomes definitely false → bool_var = 0
    3. If bool_var = 1 → enforce comparison
    4. If bool_var = 0 → enforce negation of comparison
    """
    
    def __init__(self, bool_var: str, lhs_var: str, op: CmpOp, rhs_var: str):
        """
        Initialize comparison reifier.
        
        Args:
            bool_var: Boolean result variable (domain should be {0, 1})
            lhs_var: Left-hand side variable
            op: Comparison operator
            rhs_var: Right-hand side variable
        """
        self.bool_var = bool_var
        self.lhs_var = lhs_var
        self.op = op
        self.rhs_var = rhs_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Propagate reification constraint bidirectionally."""
        bool_v = variables.get(self.bool_var)
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([bool_v, lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if any(v.domain.is_empty() for v in [bool_v, lhs, rhs]):
            return PropagationResult.conflict()
        
        changed = set()
        
        # Direction 1: Comparison state → bool_var
        # If comparison is definitely true, bool_var must be 1
        if self._is_definitely_true(lhs.domain, rhs.domain):
            new_bool = bool_v.domain.intersect(
                IntDomain([(1, 1)], bool_v.domain.width, bool_v.domain.signed)
            )
            if new_bool.is_empty():
                return PropagationResult.conflict()
            if new_bool != bool_v.domain:
                bool_v.domain = new_bool
                changed.add(bool_v)
        
        # If comparison is definitely false, bool_var must be 0
        elif self._is_definitely_false(lhs.domain, rhs.domain):
            new_bool = bool_v.domain.intersect(
                IntDomain([(0, 0)], bool_v.domain.width, bool_v.domain.signed)
            )
            if new_bool.is_empty():
                return PropagationResult.conflict()
            if new_bool != bool_v.domain:
                bool_v.domain = new_bool
                changed.add(bool_v)
        
        # Direction 2: bool_var → Comparison enforcement
        # If bool_var = 1 (true), enforce the comparison
        if bool_v.domain.is_singleton() and 1 in bool_v.domain.values():
            lhs_new, rhs_new = self._enforce_comparison(lhs.domain, rhs.domain, self.op)
            
            if lhs_new.is_empty() or rhs_new.is_empty():
                return PropagationResult.conflict()
            
            if lhs_new != lhs.domain:
                lhs.domain = lhs_new
                changed.add(lhs)
            if rhs_new != rhs.domain:
                rhs.domain = rhs_new
                changed.add(rhs)
        
        # If bool_var = 0 (false), enforce the negation
        elif bool_v.domain.is_singleton() and 0 in bool_v.domain.values():
            lhs_new, rhs_new = self._enforce_negation(lhs.domain, rhs.domain, self.op)
            
            if lhs_new.is_empty() or rhs_new.is_empty():
                return PropagationResult.conflict()
            
            if lhs_new != lhs.domain:
                lhs.domain = lhs_new
                changed.add(lhs)
            if rhs_new != rhs.domain:
                rhs.domain = rhs_new
                changed.add(rhs)
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def _is_definitely_true(self, lhs_domain: IntDomain, rhs_domain: IntDomain) -> bool:
        """Check if comparison is definitely true for all values in domains."""
        if self.op == CmpOp.Eq:
            # Equal: true if both domains are singleton and equal
            return lhs_domain.is_singleton() and rhs_domain.is_singleton() and \
                   list(lhs_domain.values())[0] == list(rhs_domain.values())[0]
        elif self.op == CmpOp.NotEq:
            # Not equal: true if domains don't overlap
            return lhs_domain.intersect(rhs_domain).is_empty()
        elif self.op == CmpOp.Lt:
            # Less than: true if max(lhs) < min(rhs)
            lhs_max = max(lhs_domain.values())
            rhs_min = min(rhs_domain.values())
            return lhs_max < rhs_min
        elif self.op == CmpOp.LtE:
            # Less than or equal: true if max(lhs) <= min(rhs)
            lhs_max = max(lhs_domain.values())
            rhs_min = min(rhs_domain.values())
            return lhs_max <= rhs_min
        elif self.op == CmpOp.Gt:
            # Greater than: true if min(lhs) > max(rhs)
            lhs_min = min(lhs_domain.values())
            rhs_max = max(rhs_domain.values())
            return lhs_min > rhs_max
        elif self.op == CmpOp.GtE:
            # Greater than or equal: true if min(lhs) >= max(rhs)
            lhs_min = min(lhs_domain.values())
            rhs_max = max(rhs_domain.values())
            return lhs_min >= rhs_max
        return False
    
    def _is_definitely_false(self, lhs_domain: IntDomain, rhs_domain: IntDomain) -> bool:
        """Check if comparison is definitely false for all values in domains."""
        # A comparison is false if its negation is definitely true
        negated_op = {
            CmpOp.Eq: CmpOp.NotEq,
            CmpOp.NotEq: CmpOp.Eq,
            CmpOp.Lt: CmpOp.GtE,
            CmpOp.LtE: CmpOp.Gt,
            CmpOp.Gt: CmpOp.LtE,
            CmpOp.GtE: CmpOp.Lt,
        }
        old_op = self.op
        self.op = negated_op[old_op]
        result = self._is_definitely_true(lhs_domain, rhs_domain)
        self.op = old_op
        return result
    
    def _enforce_comparison(self, lhs_domain: IntDomain, rhs_domain: IntDomain, op: CmpOp) -> tuple:
        """Enforce the comparison by filtering domains."""
        # For simplicity, enumerate valid combinations (works for small domains)
        if lhs_domain.size() <= 100 and rhs_domain.size() <= 100:
            valid_lhs = set()
            valid_rhs = set()
            
            for lhs_val in lhs_domain.values():
                for rhs_val in rhs_domain.values():
                    if self._check_comparison(lhs_val, op, rhs_val):
                        valid_lhs.add(lhs_val)
                        valid_rhs.add(rhs_val)
            
            if valid_lhs and valid_rhs:
                lhs_new = self._values_to_domain(valid_lhs, lhs_domain.width, lhs_domain.signed)
                rhs_new = self._values_to_domain(valid_rhs, rhs_domain.width, rhs_domain.signed)
                return lhs_domain.intersect(lhs_new), rhs_domain.intersect(rhs_new)
        
        # For large domains, return unchanged (conservative)
        return lhs_domain, rhs_domain
    
    def _enforce_negation(self, lhs_domain: IntDomain, rhs_domain: IntDomain, op: CmpOp) -> tuple:
        """Enforce the negation of the comparison."""
        negated_op = {
            CmpOp.Eq: CmpOp.NotEq,
            CmpOp.NotEq: CmpOp.Eq,
            CmpOp.Lt: CmpOp.GtE,
            CmpOp.LtE: CmpOp.Gt,
            CmpOp.Gt: CmpOp.LtE,
            CmpOp.GtE: CmpOp.Lt,
        }
        return self._enforce_comparison(lhs_domain, rhs_domain, negated_op[op])
    
    def _check_comparison(self, lhs: int, op: CmpOp, rhs: int) -> bool:
        """Check if a comparison holds for specific values."""
        if op == CmpOp.Eq:
            return lhs == rhs
        elif op == CmpOp.NotEq:
            return lhs != rhs
        elif op == CmpOp.Lt:
            return lhs < rhs
        elif op == CmpOp.LtE:
            return lhs <= rhs
        elif op == CmpOp.Gt:
            return lhs > rhs
        elif op == CmpOp.GtE:
            return lhs >= rhs
        return False
    
    def _values_to_domain(self, values: Set[int], width: int, signed: bool) -> IntDomain:
        """Convert a set of values to an IntDomain."""
        if not values:
            return IntDomain([], width, signed)
        
        sorted_vals = sorted(values)
        intervals = []
        start = sorted_vals[0]
        end = sorted_vals[0]
        
        for val in sorted_vals[1:]:
            if val == end + 1:
                end = val
            else:
                intervals.append((start, end))
                start = val
                end = val
        intervals.append((start, end))
        
        return IntDomain(intervals, width, signed)
    
    def affected_variables(self) -> Set[str]:
        return {self.bool_var, self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.bool_var, self.lhs_var, self.rhs_var]):
            return False
        
        bool_val = assignment[self.bool_var]
        comp_result = self._check_comparison(
            assignment[self.lhs_var],
            self.op,
            assignment[self.rhs_var]
        )
        
        return (bool_val == 1) == comp_result
