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
from zuspec.ir.core.expr import CmpOp


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
        lhs_lo = lhs_domain.intervals[0][0] if lhs_domain.intervals else None
        lhs_hi = lhs_domain.intervals[-1][1] if lhs_domain.intervals else None
        rhs_lo = rhs_domain.intervals[0][0] if rhs_domain.intervals else None
        rhs_hi = rhs_domain.intervals[-1][1] if rhs_domain.intervals else None
        if any(v is None for v in (lhs_lo, lhs_hi, rhs_lo, rhs_hi)):
            return False
        if self.op == CmpOp.Eq:
            return lhs_domain.is_singleton() and rhs_domain.is_singleton() and lhs_lo == rhs_lo
        elif self.op == CmpOp.NotEq:
            return lhs_domain.intersect(rhs_domain).is_empty()
        elif self.op == CmpOp.Lt:
            return lhs_hi < rhs_lo
        elif self.op == CmpOp.LtE:
            return lhs_hi <= rhs_lo
        elif self.op == CmpOp.Gt:
            return lhs_lo > rhs_hi
        elif self.op == CmpOp.GtE:
            return lhs_lo >= rhs_hi
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
        # Use interval bounds for O(1) enforcement instead of enumeration.
        lhs_lo = lhs_domain.intervals[0][0] if lhs_domain.intervals else 0
        lhs_hi = lhs_domain.intervals[-1][1] if lhs_domain.intervals else 0
        rhs_lo = rhs_domain.intervals[0][0] if rhs_domain.intervals else 0
        rhs_hi = rhs_domain.intervals[-1][1] if rhs_domain.intervals else 0

        new_lhs = lhs_domain
        new_rhs = rhs_domain

        if op == CmpOp.Lt:
            # lhs < rhs  =>  lhs <= rhs_hi-1, rhs >= lhs_lo+1
            new_lhs = lhs_domain.intersect(IntDomain([(lhs_lo, rhs_hi - 1)], lhs_domain.width, lhs_domain.signed))
            new_rhs = rhs_domain.intersect(IntDomain([(lhs_lo + 1, rhs_hi)], rhs_domain.width, rhs_domain.signed))
        elif op == CmpOp.LtE:
            # lhs <= rhs  =>  lhs <= rhs_hi, rhs >= lhs_lo
            new_lhs = lhs_domain.intersect(IntDomain([(lhs_lo, rhs_hi)], lhs_domain.width, lhs_domain.signed))
            new_rhs = rhs_domain.intersect(IntDomain([(lhs_lo, rhs_hi)], rhs_domain.width, rhs_domain.signed))
        elif op == CmpOp.Gt:
            # lhs > rhs  =>  lhs >= rhs_lo+1, rhs <= lhs_hi-1
            new_lhs = lhs_domain.intersect(IntDomain([(rhs_lo + 1, lhs_hi)], lhs_domain.width, lhs_domain.signed))
            new_rhs = rhs_domain.intersect(IntDomain([(rhs_lo, lhs_hi - 1)], rhs_domain.width, rhs_domain.signed))
        elif op == CmpOp.GtE:
            # lhs >= rhs  =>  lhs >= rhs_lo, rhs <= lhs_hi
            new_lhs = lhs_domain.intersect(IntDomain([(rhs_lo, lhs_hi)], lhs_domain.width, lhs_domain.signed))
            new_rhs = rhs_domain.intersect(IntDomain([(rhs_lo, lhs_hi)], rhs_domain.width, rhs_domain.signed))
        elif op == CmpOp.Eq:
            inter = lhs_domain.intersect(rhs_domain)
            new_lhs = inter
            new_rhs = inter
        elif op == CmpOp.NotEq:
            # Can only prune if one side is singleton
            if lhs_domain.is_singleton():
                val = lhs_domain.intervals[0][0]
                new_rhs = rhs_domain.copy()
                new_rhs.remove_value(val)
            if rhs_domain.is_singleton():
                val = rhs_domain.intervals[0][0]
                new_lhs = lhs_domain.copy()
                new_lhs.remove_value(val)

        return new_lhs, new_rhs
    
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


class DisjunctiveComparisonPropagator(Propagator):
    """Enforces (C1) OR (C2) OR ... OR (Cn) without reification.

    Each Ci is a simple comparison (lhs_i op_i rhs_i).  When all disjuncts
    except one are definitely false, the remaining disjunct is enforced
    directly via interval bounds.  This avoids creating intermediate boolean
    variables and the per-round reification overhead.

    Handles any number of disjuncts (2, 3, ...).
    """

    _NEGATED = {
        CmpOp.Eq: CmpOp.NotEq, CmpOp.NotEq: CmpOp.Eq,
        CmpOp.Lt: CmpOp.GtE, CmpOp.LtE: CmpOp.Gt,
        CmpOp.Gt: CmpOp.LtE, CmpOp.GtE: CmpOp.Lt,
    }

    def __init__(self, clauses):
        """Args:
            clauses: list of (lhs_var_name, CmpOp, rhs_var_name) tuples.
        """
        self.clauses = clauses  # [(lhs, op, rhs), ...]
        self._vars = set()
        for lhs, _, rhs in clauses:
            self._vars.add(lhs)
            self._vars.add(rhs)

    def propagate(self, variables):
        # Resolve variable objects once
        resolved = []
        for lhs, op, rhs in self.clauses:
            vl = variables.get(lhs)
            vr = variables.get(rhs)
            if vl is None or vr is None:
                return PropagationResult.fixed_point()
            if vl.domain.is_empty() or vr.domain.is_empty():
                return PropagationResult.conflict()
            resolved.append((vl, op, vr))

        # Determine which disjuncts are definitely false
        false_flags = [self._definitely_false(vl.domain, op, vr.domain)
                       for vl, op, vr in resolved]
        n_false = sum(false_flags)
        n_total = len(self.clauses)

        if n_false == n_total:
            return PropagationResult.conflict()

        # Only enforce when exactly one disjunct is not definitely false
        if n_false < n_total - 1:
            return PropagationResult.fixed_point()

        # Find the single surviving disjunct and enforce it
        changed = set()
        for i, (vl, op, vr) in enumerate(resolved):
            if false_flags[i]:
                continue
            new_l, new_r = self._enforce(vl.domain, op, vr.domain)
            if new_l.is_empty() or new_r.is_empty():
                return PropagationResult.conflict()
            if new_l != vl.domain:
                vl.domain = new_l; changed.add(vl)
            if new_r != vr.domain:
                vr.domain = new_r; changed.add(vr)
            break  # only one survivor

        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()

    # -- helpers (static-ish, no per-instance state) -----------------------

    def _definitely_false(self, ld, op, rd):
        """True when ``lhs op rhs`` is false for ALL values in the domains."""
        if ld.is_empty() or rd.is_empty():
            return True
        l_lo, l_hi = ld.intervals[0][0], ld.intervals[-1][1]
        r_lo, r_hi = rd.intervals[0][0], rd.intervals[-1][1]
        neg = self._NEGATED[op]
        if neg == CmpOp.Lt:   return l_hi < r_lo
        if neg == CmpOp.LtE:  return l_hi <= r_lo
        if neg == CmpOp.Gt:   return l_lo > r_hi
        if neg == CmpOp.GtE:  return l_lo >= r_hi
        if neg == CmpOp.Eq:
            return ld.is_singleton() and rd.is_singleton() and l_lo == r_lo
        if neg == CmpOp.NotEq:
            return ld.intersect(rd).is_empty()
        return False

    def _enforce(self, ld, op, rd):
        """Tighten domains so ``lhs op rhs`` can hold."""
        l_lo = ld.intervals[0][0] if ld.intervals else 0
        l_hi = ld.intervals[-1][1] if ld.intervals else 0
        r_lo = rd.intervals[0][0] if rd.intervals else 0
        r_hi = rd.intervals[-1][1] if rd.intervals else 0
        new_l, new_r = ld, rd
        if op == CmpOp.Lt:
            new_l = ld.intersect(IntDomain([(l_lo, r_hi - 1)], ld.width, ld.signed))
            new_r = rd.intersect(IntDomain([(l_lo + 1, r_hi)], rd.width, rd.signed))
        elif op == CmpOp.LtE:
            new_l = ld.intersect(IntDomain([(l_lo, r_hi)], ld.width, ld.signed))
            new_r = rd.intersect(IntDomain([(l_lo, r_hi)], rd.width, rd.signed))
        elif op == CmpOp.Gt:
            new_l = ld.intersect(IntDomain([(r_lo + 1, l_hi)], ld.width, ld.signed))
            new_r = rd.intersect(IntDomain([(r_lo, l_hi - 1)], rd.width, rd.signed))
        elif op == CmpOp.GtE:
            new_l = ld.intersect(IntDomain([(r_lo, l_hi)], ld.width, ld.signed))
            new_r = rd.intersect(IntDomain([(r_lo, l_hi)], rd.width, rd.signed))
        elif op == CmpOp.Eq:
            inter = ld.intersect(rd)
            new_l = inter; new_r = inter
        elif op == CmpOp.NotEq:
            if ld.is_singleton():
                new_r = rd.copy(); new_r.remove_value(ld.intervals[0][0])
            if rd.is_singleton():
                new_l = ld.copy(); new_l.remove_value(rd.intervals[0][0])
        return new_l, new_r

    def affected_variables(self):
        return self._vars

    def is_satisfied(self, assignment):
        for lhs, op, rhs in self.clauses:
            a, b = assignment.get(lhs), assignment.get(rhs)
            if a is None or b is None:
                continue
            ok = False
            if op == CmpOp.Eq:    ok = (a == b)
            elif op == CmpOp.NotEq: ok = (a != b)
            elif op == CmpOp.Lt:    ok = (a < b)
            elif op == CmpOp.LtE:   ok = (a <= b)
            elif op == CmpOp.Gt:    ok = (a > b)
            elif op == CmpOp.GtE:   ok = (a >= b)
            if ok:
                return True
        return False
