"""Tests for constraint propagators."""

import pytest
from zuspec.dataclasses.solver.propagators import (
    AddPropagator,
    SubPropagator,
    MultPropagator,
    DivPropagator,
    ModPropagator,
    EqualPropagator,
    NotEqualPropagator,
    LessThanPropagator,
    LessEqualPropagator,
    GreaterThanPropagator,
    GreaterEqualPropagator,
    PropagationStatus,
)
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain


def test_equal_propagator():
    """Test equality constraint propagation."""
    x = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(5, 15)], width=32, signed=False))
    
    propagator = EqualPropagator("x", "y")
    variables = {"x": x, "y": y}
    
    result = propagator.propagate(variables)
    
    assert result.status == PropagationStatus.CONSISTENT
    # After propagation, both should have domain [5, 10] (intersection)
    assert x.domain.intervals == [(5, 10)]
    assert y.domain.intervals == [(5, 10)]


def test_equal_propagator_conflict():
    """Test equality constraint with disjoint domains."""
    x = Variable("x", domain=IntDomain([(0, 5)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(10, 15)], width=32, signed=False))
    
    propagator = EqualPropagator("x", "y")
    variables = {"x": x, "y": y}
    
    result = propagator.propagate(variables)
    
    assert result.status == PropagationStatus.CONFLICT


def test_not_equal_propagator():
    """Test inequality constraint propagation."""
    x = Variable("x", domain=IntDomain([(5, 5)], width=32, signed=False))  # Singleton
    y = Variable("y", domain=IntDomain([(0, 10)], width=32, signed=False))
    
    propagator = NotEqualPropagator("x", "y")
    variables = {"x": x, "y": y}
    
    result = propagator.propagate(variables)
    
    assert result.status == PropagationStatus.CONSISTENT
    # Value 5 should be removed from y's domain
    assert 5 not in list(y.domain.values())


def test_less_than_propagator():
    """Test less than constraint propagation."""
    x = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(5, 15)], width=32, signed=False))
    
    propagator = LessThanPropagator("x", "y")
    variables = {"x": x, "y": y}
    
    result = propagator.propagate(variables)
    
    assert result.status in [PropagationStatus.CONSISTENT, PropagationStatus.FIXED_POINT]
    # x < y, so x_max < y_min constraint should be applied
    assert x.domain.intervals[-1][1] < 15  # x must be < 15


def test_add_propagator():
    """Test addition constraint propagation."""
    result = Variable("result", domain=IntDomain([(10, 20)], width=32, signed=False))
    lhs = Variable("lhs", domain=IntDomain([(0, 15)], width=32, signed=False))
    rhs = Variable("rhs", domain=IntDomain([(0, 15)], width=32, signed=False))
    
    propagator = AddPropagator("result", "lhs", "rhs", bit_width=32)
    variables = {"result": result, "lhs": lhs, "rhs": rhs}
    
    result_prop = propagator.propagate(variables)
    
    assert result_prop.status in [PropagationStatus.CONSISTENT, PropagationStatus.FIXED_POINT]
    # Result should still be in valid range after propagation


def test_add_propagator_satisfaction():
    """Test addition constraint satisfaction check."""
    propagator = AddPropagator("result", "lhs", "rhs", bit_width=32)
    
    # 5 + 3 = 8
    assignment = {"result": 8, "lhs": 5, "rhs": 3}
    assert propagator.is_satisfied(assignment)
    
    # 5 + 3 != 9
    assignment = {"result": 9, "lhs": 5, "rhs": 3}
    assert not propagator.is_satisfied(assignment)


def test_mult_propagator_small_domain():
    """Test multiplication with small domains (exact enumeration)."""
    result = Variable("result", domain=IntDomain([(0, 100)], width=32, signed=False))
    lhs = Variable("lhs", domain=IntDomain([(2, 5)], width=32, signed=False))
    rhs = Variable("rhs", domain=IntDomain([(3, 4)], width=32, signed=False))
    
    propagator = MultPropagator("result", "lhs", "rhs", bit_width=32, small_domain_threshold=100)
    variables = {"result": result, "lhs": lhs, "rhs": rhs}
    
    result_prop = propagator.propagate(variables)
    
    assert result_prop.status in [PropagationStatus.CONSISTENT, PropagationStatus.FIXED_POINT]
    # Products are: 2*3=6, 2*4=8, 3*3=9, 3*4=12, 4*3=12, 4*4=16, 5*3=15, 5*4=20
    # So result should be constrained to [6, 20]
    assert result.domain.intervals[0][0] >= 6
    assert result.domain.intervals[-1][1] <= 20


def test_div_propagator_no_zero():
    """Test division constraint removes zero from divisor."""
    result = Variable("result", domain=IntDomain([(0, 10)], width=32, signed=False))
    lhs = Variable("lhs", domain=IntDomain([(0, 20)], width=32, signed=False))
    rhs = Variable("rhs", domain=IntDomain([(0, 5)], width=32, signed=False))
    
    propagator = DivPropagator("result", "lhs", "rhs")
    variables = {"result": result, "lhs": lhs, "rhs": rhs}
    
    result_prop = propagator.propagate(variables)
    
    assert result_prop.status in [PropagationStatus.CONSISTENT, PropagationStatus.FIXED_POINT]
    # Zero should be removed from rhs domain
    assert 0 not in list(rhs.domain.values())


def test_mod_propagator_no_zero():
    """Test modulo constraint removes zero from divisor."""
    result = Variable("result", domain=IntDomain([(0, 10)], width=32, signed=False))
    lhs = Variable("lhs", domain=IntDomain([(0, 20)], width=32, signed=False))
    rhs = Variable("rhs", domain=IntDomain([(0, 5)], width=32, signed=False))
    
    propagator = ModPropagator("result", "lhs", "rhs")
    variables = {"result": result, "lhs": lhs, "rhs": rhs}
    
    result_prop = propagator.propagate(variables)
    
    assert result_prop.status in [PropagationStatus.CONSISTENT, PropagationStatus.FIXED_POINT]
    # Zero should be removed from rhs domain
    assert 0 not in list(rhs.domain.values())


def test_sub_propagator_satisfaction():
    """Test subtraction constraint satisfaction check."""
    propagator = SubPropagator("result", "lhs", "rhs", bit_width=32)
    
    # 10 - 3 = 7
    assignment = {"result": 7, "lhs": 10, "rhs": 3}
    assert propagator.is_satisfied(assignment)
    
    # 10 - 3 != 6
    assignment = {"result": 6, "lhs": 10, "rhs": 3}
    assert not propagator.is_satisfied(assignment)
