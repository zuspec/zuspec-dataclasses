"""Tests for uniqueness (AllDifferent) constraint propagators"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.propagators.uniqueness import (
    UniquePropagator,
    PairwiseUniquePropagator,
)


def test_unique_basic():
    """Test basic uniqueness constraint"""
    # unique {x, y, z}, all = [0, 10]
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    y = Variable("y", IntDomain([(0, 10)], width=8, signed=False))
    z = Variable("z", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z}
    
    prop = UniquePropagator(["x", "y", "z"])
    result = prop.propagate(variables)
    
    # Initially no propagation (all unassigned)
    assert result.is_fixed_point()


def test_unique_assigned_removes_value():
    """Test that assigning a variable removes its value from others"""
    # unique {x, y, z}, x = 5, y = [0, 10], z = [0, 10]
    x = Variable("x", IntDomain([(5, 5)], width=8, signed=False))
    x.current_value = 5
    y = Variable("y", IntDomain([(0, 10)], width=8, signed=False))
    z = Variable("z", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z}
    
    prop = UniquePropagator(["x", "y", "z"])
    result = prop.propagate(variables)
    
    # y and z should have 5 removed
    assert not result.is_conflict()
    assert 5 not in list(y.domain.values())
    assert 5 not in list(z.domain.values())


def test_unique_multiple_assigned():
    """Test with multiple variables assigned"""
    # unique {x, y, z}, x = 3, y = 7, z = [0, 10]
    x = Variable("x", IntDomain([(3, 3)], width=8, signed=False))
    x.current_value = 3
    y = Variable("y", IntDomain([(7, 7)], width=8, signed=False))
    y.current_value = 7
    z = Variable("z", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z}
    
    prop = UniquePropagator(["x", "y", "z"])
    result = prop.propagate(variables)
    
    # z should have 3 and 7 removed
    assert not result.is_conflict()
    z_values = set(z.domain.values())
    assert 3 not in z_values
    assert 7 not in z_values


def test_unique_conflict_no_values():
    """Test conflict when assigned value causes empty domain"""
    # unique {x, y}, x = 5, y = [5, 5]
    x = Variable("x", IntDomain([(5, 5)], width=8, signed=False))
    x.current_value = 5
    y = Variable("y", IntDomain([(5, 5)], width=8, signed=False))
    variables = {"x": x, "y": y}
    
    prop = UniquePropagator(["x", "y"])
    result = prop.propagate(variables)
    
    # Should detect conflict (y has no other values)
    assert result.is_conflict()


def test_unique_pigeonhole_conflict():
    """Test pigeonhole principle detection"""
    # unique {x, y, z}, all have domain [0, 1] (3 vars, 2 values)
    x = Variable("x", IntDomain([(0, 1)], width=8, signed=False))
    y = Variable("y", IntDomain([(0, 1)], width=8, signed=False))
    z = Variable("z", IntDomain([(0, 1)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z}
    
    prop = UniquePropagator(["x", "y", "z"])
    result = prop.propagate(variables)
    
    # Should detect conflict (3 variables, only 2 values available)
    assert result.is_conflict()


def test_unique_no_pigeonhole_conflict():
    """Test that enough values avoids pigeonhole conflict"""
    # unique {x, y, z}, all have domain [0, 2] (3 vars, 3 values)
    x = Variable("x", IntDomain([(0, 2)], width=8, signed=False))
    y = Variable("y", IntDomain([(0, 2)], width=8, signed=False))
    z = Variable("z", IntDomain([(0, 2)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z}
    
    prop = UniquePropagator(["x", "y", "z"])
    result = prop.propagate(variables)
    
    # Should not conflict (exactly enough values)
    assert not result.is_conflict()


def test_unique_is_satisfied():
    """Test is_satisfied method"""
    prop = UniquePropagator(["x", "y", "z"])
    
    # All different
    assert prop.is_satisfied({"x": 1, "y": 2, "z": 3})
    
    # x and y same
    assert not prop.is_satisfied({"x": 1, "y": 1, "z": 3})
    
    # All same
    assert not prop.is_satisfied({"x": 5, "y": 5, "z": 5})


def test_unique_affected_variables():
    """Test affected_variables method"""
    prop = UniquePropagator(["a", "b", "c", "d"])
    assert prop.affected_variables() == {"a", "b", "c", "d"}


def test_unique_requires_multiple_vars():
    """Test that uniqueness requires at least 2 variables"""
    with pytest.raises(ValueError, match="at least 2 variables"):
        UniquePropagator(["x"])


def test_pairwise_unique_basic():
    """Test pairwise uniqueness"""
    # x != y, x = [0, 5], y = [0, 5]
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False))
    y = Variable("y", IntDomain([(0, 5)], width=8, signed=False))
    variables = {"x": x, "y": y}
    
    prop = PairwiseUniquePropagator("x", "y")
    result = prop.propagate(variables)
    
    # No propagation yet (both unassigned)
    assert result.is_fixed_point()


def test_pairwise_unique_x_assigned():
    """Test pairwise with x assigned"""
    # x != y, x = 3, y = [0, 5]
    x = Variable("x", IntDomain([(3, 3)], width=8, signed=False))
    x.current_value = 3
    y = Variable("y", IntDomain([(0, 5)], width=8, signed=False))
    variables = {"x": x, "y": y}
    
    prop = PairwiseUniquePropagator("x", "y")
    result = prop.propagate(variables)
    
    # y should have 3 removed
    assert not result.is_conflict()
    assert 3 not in list(y.domain.values())


def test_pairwise_unique_y_assigned():
    """Test pairwise with y assigned"""
    # x != y, x = [0, 5], y = 2
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False))
    y = Variable("y", IntDomain([(2, 2)], width=8, signed=False))
    y.current_value = 2
    variables = {"x": x, "y": y}
    
    prop = PairwiseUniquePropagator("x", "y")
    result = prop.propagate(variables)
    
    # x should have 2 removed
    assert not result.is_conflict()
    assert 2 not in list(x.domain.values())


def test_pairwise_unique_singleton_conflict():
    """Test pairwise conflict with singleton domains"""
    # x != y, x = [5, 5], y = [5, 5]
    x = Variable("x", IntDomain([(5, 5)], width=8, signed=False))
    y = Variable("y", IntDomain([(5, 5)], width=8, signed=False))
    variables = {"x": x, "y": y}
    
    prop = PairwiseUniquePropagator("x", "y")
    result = prop.propagate(variables)
    
    # Should detect conflict (both must be 5)
    assert result.is_conflict()


def test_pairwise_unique_is_satisfied():
    """Test is_satisfied for pairwise"""
    prop = PairwiseUniquePropagator("x", "y")
    
    assert prop.is_satisfied({"x": 1, "y": 2})
    assert prop.is_satisfied({"x": 5, "y": 3})
    assert not prop.is_satisfied({"x": 5, "y": 5})


def test_pairwise_unique_affected_variables():
    """Test affected_variables for pairwise"""
    prop = PairwiseUniquePropagator("a", "b")
    assert prop.affected_variables() == {"a", "b"}


def test_unique_repr():
    """Test string representation"""
    prop = UniquePropagator(["x", "y", "z"])
    repr_str = repr(prop)
    assert "UniquePropagator" in repr_str
    assert "x" in repr_str
    assert "y" in repr_str
    assert "z" in repr_str


def test_pairwise_repr():
    """Test pairwise string representation"""
    prop = PairwiseUniquePropagator("x", "y")
    repr_str = repr(prop)
    assert "PairwiseUnique" in repr_str
    assert "x" in repr_str
    assert "y" in repr_str
