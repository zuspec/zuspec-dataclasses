"""Tests for set membership constraint propagators"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.propagators.set_membership import (
    InSetPropagator,
    RangeConstraintPropagator,
)


def test_in_set_single_values():
    """Test set membership with individual values"""
    # x inside {1, 5, 10}, x = [0, 10]
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x}
    
    prop = InSetPropagator("x", [1, 5, 10], width=8)
    result = prop.propagate(variables)
    
    assert not result.is_conflict()
    assert set(x.domain.values()) == {1, 5, 10}


def test_in_set_range():
    """Test set membership with range"""
    # x inside {[2, 5]}, x = [0, 10]
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x}
    
    prop = InSetPropagator("x", [(2, 5)], width=8)
    result = prop.propagate(variables)
    
    assert not result.is_conflict()
    assert set(x.domain.values()) == {2, 3, 4, 5}


def test_in_set_mixed():
    """Test set membership with mixed values and ranges"""
    # x inside {1, [5, 7], 10}, x = [0, 12]
    x = Variable("x", IntDomain([(0, 12)], width=8, signed=False))
    variables = {"x": x}
    
    prop = InSetPropagator("x", [1, (5, 7), 10], width=8)
    result = prop.propagate(variables)
    
    assert not result.is_conflict()
    assert set(x.domain.values()) == {1, 5, 6, 7, 10}


def test_in_set_negated():
    """Test negated set membership: !(x inside {...})"""
    # !(x inside {2, 3, 4}), x = [0, 5]
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False))
    variables = {"x": x}
    
    prop = InSetPropagator("x", [2, 3, 4], width=8, negated=True)
    result = prop.propagate(variables)
    
    assert not result.is_conflict()
    assert set(x.domain.values()) == {0, 1, 5}


def test_in_set_conflict():
    """Test conflict when no overlap"""
    # x inside {10, 20, 30}, x = [0, 5]
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False))
    variables = {"x": x}
    
    prop = InSetPropagator("x", [10, 20, 30], width=8)
    result = prop.propagate(variables)
    
    assert result.is_conflict()


def test_in_set_already_satisfied():
    """Test when domain is already subset of set"""
    # x inside {[0, 10]}, x = [2, 5]
    x = Variable("x", IntDomain([(2, 5)], width=8, signed=False))
    variables = {"x": x}
    
    prop = InSetPropagator("x", [(0, 10)], width=8)
    result = prop.propagate(variables)
    
    # No change needed
    assert result.is_fixed_point()
    assert set(x.domain.values()) == {2, 3, 4, 5}


def test_in_set_is_satisfied():
    """Test is_satisfied method"""
    prop = InSetPropagator("x", [1, 5, 10], width=8)
    
    assert prop.is_satisfied({"x": 1})
    assert prop.is_satisfied({"x": 5})
    assert prop.is_satisfied({"x": 10})
    assert not prop.is_satisfied({"x": 2})
    assert not prop.is_satisfied({"x": 0})


def test_in_set_negated_is_satisfied():
    """Test is_satisfied for negated set"""
    prop = InSetPropagator("x", [1, 5, 10], width=8, negated=True)
    
    assert not prop.is_satisfied({"x": 1})
    assert not prop.is_satisfied({"x": 5})
    assert not prop.is_satisfied({"x": 10})
    assert prop.is_satisfied({"x": 2})
    assert prop.is_satisfied({"x": 0})


def test_in_set_overlapping_ranges():
    """Test with overlapping ranges that should be merged"""
    # x inside {[0, 5], [3, 8]}, x = [0, 10]
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x}
    
    prop = InSetPropagator("x", [(0, 5), (3, 8)], width=8)
    result = prop.propagate(variables)
    
    assert not result.is_conflict()
    # Should merge to [0, 8]
    assert set(x.domain.values()) == {0, 1, 2, 3, 4, 5, 6, 7, 8}


def test_in_set_empty_set():
    """Test with empty set"""
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x}
    
    prop = InSetPropagator("x", [], width=8)
    result = prop.propagate(variables)
    
    # Empty set should cause conflict
    assert result.is_conflict()


def test_range_constraint_basic():
    """Test simple range constraint"""
    # 2 <= x <= 5, x = [0, 10]
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x}
    
    prop = RangeConstraintPropagator("x", low=2, high=5, width=8)
    result = prop.propagate(variables)
    
    assert not result.is_conflict()
    assert set(x.domain.values()) == {2, 3, 4, 5}


def test_range_constraint_no_overlap():
    """Test range constraint with no overlap"""
    # 20 <= x <= 30, x = [0, 10]
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x}
    
    prop = RangeConstraintPropagator("x", low=20, high=30, width=8)
    result = prop.propagate(variables)
    
    assert result.is_conflict()


def test_range_constraint_is_satisfied():
    """Test is_satisfied for range constraint"""
    prop = RangeConstraintPropagator("x", low=5, high=10, width=8)
    
    assert prop.is_satisfied({"x": 5})
    assert prop.is_satisfied({"x": 7})
    assert prop.is_satisfied({"x": 10})
    assert not prop.is_satisfied({"x": 4})
    assert not prop.is_satisfied({"x": 11})


def test_in_set_affected_variables():
    """Test affected_variables method"""
    prop = InSetPropagator("x", [1, 5, 10], width=8)
    assert prop.affected_variables() == {"x"}


def test_in_set_repr():
    """Test string representation"""
    prop = InSetPropagator("x", [1, 5, (10, 15)], width=8)
    repr_str = repr(prop)
    assert "InSetPropagator" in repr_str
    assert "x" in repr_str


def test_range_constraint_repr():
    """Test range constraint string representation"""
    prop = RangeConstraintPropagator("x", low=5, high=10, width=8)
    repr_str = repr(prop)
    assert "RangeConstraint" in repr_str
    assert "x" in repr_str
