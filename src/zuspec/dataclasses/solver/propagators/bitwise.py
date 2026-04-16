"""Bitwise and shift propagators for the Python solver."""

from typing import Dict, Set
from ..core.variable import Variable
from ..core.domain import IntDomain
from .base import Propagator, PropagationResult


def _tighten(var, lo, hi):
    """Intersect var.domain with [lo, hi]. Returns (changed, conflict)."""
    old = var.domain
    new = old.intersect(IntDomain([(lo, hi)], old.width, old.signed))
    if new.is_empty():
        return False, True
    if new != old:
        var.domain = new
        return True, False
    return False, False


def _singleton_result(variables, rvar, lvar, rhs_var, op_fn):
    """If both operands are singletons, tighten result to op_fn(a, b)."""
    r = variables[rvar]; a = variables[lvar]; b = variables[rhs_var]
    if a.domain.is_singleton() and b.domain.is_singleton():
        val = op_fn(a.domain.min_val, b.domain.min_val)
        ch, conf = _tighten(r, val, val)
        if conf:
            return PropagationResult.conflict()
        if ch:
            return PropagationResult.consistent({r})
    return PropagationResult.fixed_point()


class _BitwiseTernary(Propagator):
    """Base for ternary (r = a OP b) bitwise propagators."""

    def __init__(self, result_var, lhs_var, rhs_var, bit_width=64):
        self.result_var = result_var
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
        self.bit_width = bit_width

    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.lhs_var, self.rhs_var}


class BitAndPropagator(_BitwiseTernary):
    """r = a & b."""

    def propagate(self, variables):
        r = variables.get(self.result_var)
        a = variables.get(self.lhs_var)
        b = variables.get(self.rhs_var)
        if not all([r, a, b]):
            return PropagationResult.fixed_point()
        changed = set()
        new_hi = min(a.domain.max_val, b.domain.max_val)
        ch, conf = _tighten(r, r.domain.min_val, new_hi)
        if conf: return PropagationResult.conflict()
        if ch: changed.add(r)
        res = _singleton_result(variables, self.result_var, self.lhs_var,
                                self.rhs_var, lambda x, y: x & y)
        if res.is_conflict(): return res
        if res.is_consistent(): changed.update(res.changed_vars)
        return PropagationResult.consistent(changed) if changed else PropagationResult.fixed_point()

    def is_satisfied(self, assignment):
        return all(v in assignment for v in self.affected_variables()) and \
               assignment[self.result_var] == (assignment[self.lhs_var] & assignment[self.rhs_var])


class BitOrPropagator(_BitwiseTernary):
    """r = a | b."""

    def propagate(self, variables):
        return _singleton_result(variables, self.result_var, self.lhs_var,
                                 self.rhs_var, lambda x, y: x | y)

    def is_satisfied(self, assignment):
        return all(v in assignment for v in self.affected_variables()) and \
               assignment[self.result_var] == (assignment[self.lhs_var] | assignment[self.rhs_var])


class BitXorPropagator(_BitwiseTernary):
    """r = a ^ b."""

    def propagate(self, variables):
        return _singleton_result(variables, self.result_var, self.lhs_var,
                                 self.rhs_var, lambda x, y: x ^ y)

    def is_satisfied(self, assignment):
        return all(v in assignment for v in self.affected_variables()) and \
               assignment[self.result_var] == (assignment[self.lhs_var] ^ assignment[self.rhs_var])


class LShiftPropagator(_BitwiseTernary):
    """r = a << b."""

    def propagate(self, variables):
        mask = (1 << self.bit_width) - 1
        return _singleton_result(variables, self.result_var, self.lhs_var,
                                 self.rhs_var, lambda x, y: (x << y) & mask)

    def is_satisfied(self, assignment):
        if not all(v in assignment for v in self.affected_variables()):
            return False
        mask = (1 << self.bit_width) - 1
        return assignment[self.result_var] == ((assignment[self.lhs_var] << assignment[self.rhs_var]) & mask)


class RShiftPropagator(_BitwiseTernary):
    """r = a >> b."""

    def propagate(self, variables):
        return _singleton_result(variables, self.result_var, self.lhs_var,
                                 self.rhs_var, lambda x, y: x >> y)

    def is_satisfied(self, assignment):
        return all(v in assignment for v in self.affected_variables()) and \
               assignment[self.result_var] == (assignment[self.lhs_var] >> assignment[self.rhs_var])


class FloorDivPropagator(_BitwiseTernary):
    """r = a // b."""

    def propagate(self, variables):
        r = variables.get(self.result_var)
        a = variables.get(self.lhs_var)
        b = variables.get(self.rhs_var)
        if not all([r, a, b]):
            return PropagationResult.fixed_point()
        changed = set()
        if b.domain.min_val > 0:
            new_lo = a.domain.min_val // b.domain.max_val
            new_hi = a.domain.max_val // b.domain.min_val
            ch, conf = _tighten(r, new_lo, new_hi)
            if conf: return PropagationResult.conflict()
            if ch: changed.add(r)
        res = _singleton_result(
            variables, self.result_var, self.lhs_var, self.rhs_var,
            lambda x, y: x // y if y != 0 else 0)
        if res.is_conflict(): return res
        if res.is_consistent(): changed.update(res.changed_vars)
        return PropagationResult.consistent(changed) if changed else PropagationResult.fixed_point()

    def is_satisfied(self, assignment):
        if not all(v in assignment for v in self.affected_variables()):
            return False
        b = assignment[self.rhs_var]
        return b != 0 and assignment[self.result_var] == (assignment[self.lhs_var] // b)
