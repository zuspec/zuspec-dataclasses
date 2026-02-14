"""Tests for implication constraint propagators"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.propagators.implication import (
    ImplicationPropagator,
)
from zuspec.dataclasses.solver.propagators.relational import EqualPropagator


def test_implication_condition_true_enforces_consequence():
    """Test that when condition is true, consequence must be true"""
    # cond -> cons, cond = 1, cons = {0, 1}
    cond = Variable("cond", IntDomain([(1, 1)], width=1, signed=False))
    cons = Variable("cons", IntDomain([(0, 1)], width=1, signed=False))
    variables = {"cond": cond, "cons": cons}
    
    prop = ImplicationPropagator("cond", "cons")
    result = prop.propagate(variables)
    
    # Consequence should be forced to 1
    assert not result.is_conflict()
    assert list(cons.domain.values()) == [1]


def test_implication_consequence_false_enforces_not_condition():
    """Test that when consequence is false, condition must be false"""
    # cond -> cons, cond = {0, 1}, cons = 0
    cond = Variable("cond", IntDomain([(0, 1)], width=1, signed=False))
    cons = Variable("cons", IntDomain([(0, 0)], width=1, signed=False))
    variables = {"cond": cond, "cons": cons}
    
    prop = ImplicationPropagator("cond", "cons")
    result = prop.propagate(variables)
    
    # Condition should be forced to 0
    assert not result.is_conflict()
    assert list(cond.domain.values()) == [0]


def test_implication_both_uncertain_no_propagation():
    """Test that when both can be true or false, no propagation occurs"""
    # cond -> cons, cond = {0, 1}, cons = {0, 1}
    cond = Variable("cond", IntDomain([(0, 1)], width=1, signed=False))
    cons = Variable("cons", IntDomain([(0, 1)], width=1, signed=False))
    variables = {"cond": cond, "cons": cons}
    
    prop = ImplicationPropagator("cond", "cons")
    result = prop.propagate(variables)
    
    # No change expected
    assert result.is_fixed_point()
    assert list(cond.domain.values()) == [0, 1]
    assert list(cons.domain.values()) == [0, 1]


def test_implication_condition_false_satisfied():
    """Test that when condition is false, implication is satisfied"""
    # cond -> cons, cond = 0, cons = {0, 1}
    cond = Variable("cond", IntDomain([(0, 0)], width=1, signed=False))
    cons = Variable("cons", IntDomain([(0, 1)], width=1, signed=False))
    variables = {"cond": cond, "cons": cons}
    
    prop = ImplicationPropagator("cond", "cons")
    result = prop.propagate(variables)
    
    # No change, already satisfied (false -> anything is true)
    assert result.is_fixed_point()


def test_implication_conflict():
    """Test that condition=true and consequence=false causes conflict"""
    # cond -> cons, cond = 1, cons = 0
    cond = Variable("cond", IntDomain([(1, 1)], width=1, signed=False))
    cons = Variable("cons", IntDomain([(0, 0)], width=1, signed=False))
    variables = {"cond": cond, "cons": cons}
    
    prop = ImplicationPropagator("cond", "cons")
    result = prop.propagate(variables)
    
    # Should detect conflict
    assert result.is_conflict()


def test_implication_is_satisfied():
    """Test is_satisfied method"""
    prop = ImplicationPropagator("cond", "cons")
    
    # True -> True = True
    assert prop.is_satisfied({"cond": 1, "cons": 1})
    
    # True -> False = False
    assert not prop.is_satisfied({"cond": 1, "cons": 0})
    
    # False -> True = True
    assert prop.is_satisfied({"cond": 0, "cons": 1})
    
    # False -> False = True
    assert prop.is_satisfied({"cond": 0, "cons": 0})


def test_implication_propagation_sequence():
    """Test propagation in a sequence of steps"""
    # Start: cond = {0, 1}, cons = {0, 1}
    cond = Variable("cond", IntDomain([(0, 1)], width=1, signed=False))
    cons = Variable("cons", IntDomain([(0, 1)], width=1, signed=False))
    variables = {"cond": cond, "cons": cons}
    
    prop = ImplicationPropagator("cond", "cons")
    
    # Initially no propagation
    result = prop.propagate(variables)
    assert result.is_fixed_point()
    
    # Assign condition to true
    cond.domain = IntDomain([(1, 1)], width=1, signed=False)
    cond.current_value = 1
    
    # Now consequence should be forced to true
    result = prop.propagate(variables)
    assert not result.is_conflict()
    assert list(cons.domain.values()) == [1]


def test_implication_affected_variables():
    """Test affected_variables method"""
    prop = ImplicationPropagator("a", "b")
    assert prop.affected_variables() == {"a", "b"}


def test_implication_repr():
    """Test string representation"""
    prop = ImplicationPropagator("cond", "cons")
    repr_str = repr(prop)
    assert "ImplicationPropagator" in repr_str
    assert "cond" in repr_str
    assert "cons" in repr_str
