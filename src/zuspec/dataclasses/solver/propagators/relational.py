"""Relational constraint propagators."""

from typing import Dict, Set
from ..core.variable import Variable
from ..core.domain import IntDomain
from .base import Propagator, PropagationResult


class EqualPropagator(Propagator):
    """Propagator for equality: lhs == rhs"""
    
    def __init__(self, lhs_var: str, rhs_var: str):
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Domain intersection for equality."""
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if lhs.domain.is_empty() or rhs.domain.is_empty():
            return PropagationResult.conflict()
        
        changed = set()
        
        # Intersect domains
        old_lhs = lhs.domain
        old_rhs = rhs.domain
        
        intersection = lhs.domain.intersect(rhs.domain)
        
        if intersection.is_empty():
            return PropagationResult.conflict()
        
        lhs.domain = intersection
        rhs.domain = intersection.copy()
        
        if lhs.domain != old_lhs:
            changed.add(lhs)
        if rhs.domain != old_rhs:
            changed.add(rhs)
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return {self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.lhs_var, self.rhs_var]):
            return False
        return assignment[self.lhs_var] == assignment[self.rhs_var]


class NotEqualPropagator(Propagator):
    """Propagator for inequality: lhs != rhs"""
    
    def __init__(self, lhs_var: str, rhs_var: str):
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Remove values when one side is singleton."""
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if lhs.domain.is_empty() or rhs.domain.is_empty():
            return PropagationResult.conflict()
        
        changed = set()
        
        # If lhs is singleton, remove that value from rhs
        if lhs.domain.is_singleton():
            lhs_val = next(lhs.domain.values())
            old_rhs = rhs.domain
            if rhs.domain.remove_value(lhs_val):
                changed.add(rhs)
            
            if rhs.domain.is_empty():
                return PropagationResult.conflict()
        
        # If rhs is singleton, remove that value from lhs
        if rhs.domain.is_singleton():
            rhs_val = next(rhs.domain.values())
            old_lhs = lhs.domain
            if lhs.domain.remove_value(rhs_val):
                changed.add(lhs)
            
            if lhs.domain.is_empty():
                return PropagationResult.conflict()
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return {self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.lhs_var, self.rhs_var]):
            return False
        return assignment[self.lhs_var] != assignment[self.rhs_var]


class LessThanPropagator(Propagator):
    """Propagator for less than: lhs < rhs"""
    
    def __init__(self, lhs_var: str, rhs_var: str):
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Prune values based on < constraint."""
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if lhs.domain.is_empty() or rhs.domain.is_empty():
            return PropagationResult.conflict()
        
        changed = set()
        
        # Get bounds
        lhs_min = lhs.domain.intervals[0][0]
        lhs_max = lhs.domain.intervals[-1][1]
        rhs_min = rhs.domain.intervals[0][0]
        rhs_max = rhs.domain.intervals[-1][1]
        
        # lhs < rhs means lhs <= rhs - 1
        # So lhs_max < rhs_min is required, otherwise:
        # - Remove values from lhs >= rhs_min
        # - Remove values from rhs <= lhs_max
        
        old_lhs = lhs.domain
        old_rhs = rhs.domain
        
        # Prune lhs: lhs < rhs_max
        if lhs_max >= rhs_max:
            lhs.domain = lhs.domain.intersect(
                IntDomain([(lhs_min, rhs_max - 1)], lhs.domain.width, lhs.domain.signed)
            )
            if lhs.domain != old_lhs:
                changed.add(lhs)
        
        # Prune rhs: rhs > lhs_min
        if rhs_min <= lhs_min:
            rhs.domain = rhs.domain.intersect(
                IntDomain([(lhs_min + 1, rhs_max)], rhs.domain.width, rhs.domain.signed)
            )
            if rhs.domain != old_rhs:
                changed.add(rhs)
        
        if lhs.domain.is_empty() or rhs.domain.is_empty():
            return PropagationResult.conflict()
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return {self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.lhs_var, self.rhs_var]):
            return False
        return assignment[self.lhs_var] < assignment[self.rhs_var]


class LessEqualPropagator(Propagator):
    """Propagator for less than or equal: lhs <= rhs"""
    
    def __init__(self, lhs_var: str, rhs_var: str):
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Prune values based on <= constraint."""
        lhs = variables.get(self.lhs_var)
        rhs = variables.get(self.rhs_var)
        
        if not all([lhs, rhs]):
            return PropagationResult.fixed_point()
        
        if lhs.domain.is_empty() or rhs.domain.is_empty():
            return PropagationResult.conflict()
        
        changed = set()
        
        lhs_min = lhs.domain.intervals[0][0]
        lhs_max = lhs.domain.intervals[-1][1]
        rhs_min = rhs.domain.intervals[0][0]
        rhs_max = rhs.domain.intervals[-1][1]
        
        old_lhs = lhs.domain
        old_rhs = rhs.domain
        
        # Prune lhs: lhs <= rhs_max
        if lhs_max > rhs_max:
            lhs.domain = lhs.domain.intersect(
                IntDomain([(lhs_min, rhs_max)], lhs.domain.width, lhs.domain.signed)
            )
            if lhs.domain != old_lhs:
                changed.add(lhs)
        
        # Prune rhs: rhs >= lhs_min
        if rhs_min < lhs_min:
            rhs.domain = rhs.domain.intersect(
                IntDomain([(lhs_min, rhs_max)], rhs.domain.width, rhs.domain.signed)
            )
            if rhs.domain != old_rhs:
                changed.add(rhs)
        
        if lhs.domain.is_empty() or rhs.domain.is_empty():
            return PropagationResult.conflict()
        
        if changed:
            return PropagationResult.consistent(changed)
        return PropagationResult.fixed_point()
    
    def affected_variables(self) -> Set[str]:
        return {self.lhs_var, self.rhs_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.lhs_var, self.rhs_var]):
            return False
        return assignment[self.lhs_var] <= assignment[self.rhs_var]


class GreaterThanPropagator(Propagator):
    """Propagator for greater than: lhs > rhs"""
    
    def __init__(self, lhs_var: str, rhs_var: str):
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
        # Delegate to LessThanPropagator with swapped operands
        self._delegate = LessThanPropagator(rhs_var, lhs_var)
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        return self._delegate.propagate(variables)
    
    def affected_variables(self) -> Set[str]:
        return self._delegate.affected_variables()
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.lhs_var, self.rhs_var]):
            return False
        return assignment[self.lhs_var] > assignment[self.rhs_var]


class GreaterEqualPropagator(Propagator):
    """Propagator for greater than or equal: lhs >= rhs"""
    
    def __init__(self, lhs_var: str, rhs_var: str):
        self.lhs_var = lhs_var
        self.rhs_var = rhs_var
        # Delegate to LessEqualPropagator with swapped operands
        self._delegate = LessEqualPropagator(rhs_var, lhs_var)
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        return self._delegate.propagate(variables)
    
    def affected_variables(self) -> Set[str]:
        return self._delegate.affected_variables()
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if not all(v in assignment for v in [self.lhs_var, self.rhs_var]):
            return False
        return assignment[self.lhs_var] >= assignment[self.rhs_var]
