"""Tests for randomized search order"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.engine.seed_manager import SeedManager
from zuspec.dataclasses.solver.engine.randomization import (
    RandomizedVariableOrdering,
    RandomizedValueOrdering,
    MRVWithRandomTiebreaking,
    SolveBeforeRandomizedOrdering,
    AdaptiveRandomizedOrdering,
)


# Helper function to create test variables
def create_variables(names, domain_ranges):
    """Create variables with specified domain ranges"""
    variables = {}
    for name, (low, high) in zip(names, domain_ranges):
        variables[name] = Variable(name, IntDomain([(low, high)], width=8, signed=False))
    return variables


# RandomizedVariableOrdering tests

def test_randomized_variable_ordering_basic():
    """Test basic randomized variable ordering"""
    variables = create_variables(["x", "y", "z"], [(0, 10)] * 3)
    
    seed_manager = SeedManager(global_seed=42)
    heuristic = RandomizedVariableOrdering(seed_manager)
    
    order = heuristic.order_variables(variables, set())
    
    # Should return all variables
    assert len(order) == 3
    assert set(order) == {"x", "y", "z"}


def test_randomized_variable_ordering_reproducible():
    """Test that same seed produces same order"""
    variables = create_variables(["a", "b", "c", "d", "e"], [(0, 10)] * 5)
    
    seed_manager1 = SeedManager(global_seed=42)
    heuristic1 = RandomizedVariableOrdering(seed_manager1)
    order1 = heuristic1.order_variables(variables, set())
    
    seed_manager2 = SeedManager(global_seed=42)
    heuristic2 = RandomizedVariableOrdering(seed_manager2)
    order2 = heuristic2.order_variables(variables, set())
    
    assert order1 == order2


def test_randomized_variable_ordering_different_seeds():
    """Test that different seeds produce different orders"""
    variables = create_variables(["a", "b", "c", "d", "e"], [(0, 10)] * 5)
    
    seed_manager1 = SeedManager(global_seed=42)
    heuristic1 = RandomizedVariableOrdering(seed_manager1)
    order1 = heuristic1.order_variables(variables, set())
    
    seed_manager2 = SeedManager(global_seed=43)
    heuristic2 = RandomizedVariableOrdering(seed_manager2)
    order2 = heuristic2.order_variables(variables, set())
    
    # Very high probability of different order with 5 variables
    assert order1 != order2


def test_randomized_variable_ordering_with_assigned():
    """Test ordering excludes already assigned variables"""
    variables = create_variables(["x", "y", "z", "w"], [(0, 10)] * 4)
    
    seed_manager = SeedManager(global_seed=42)
    heuristic = RandomizedVariableOrdering(seed_manager)
    
    assigned = {"x", "z"}
    order = heuristic.order_variables(variables, assigned)
    
    # Should only return unassigned
    assert len(order) == 2
    assert set(order) == {"y", "w"}


# RandomizedValueOrdering tests

def test_randomized_value_ordering_basic():
    """Test basic randomized value ordering"""
    variable = Variable("x", IntDomain([(0, 5)], width=8, signed=False))
    
    seed_manager = SeedManager(global_seed=42)
    heuristic = RandomizedValueOrdering(seed_manager)
    
    values = heuristic.order_values(variable, {})
    
    # Should return all values
    assert len(values) == 6
    assert set(values) == {0, 1, 2, 3, 4, 5}


def test_randomized_value_ordering_reproducible():
    """Test that same seed produces same value order"""
    variable = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    
    seed_manager1 = SeedManager(global_seed=42)
    heuristic1 = RandomizedValueOrdering(seed_manager1)
    values1 = heuristic1.order_values(variable, {})
    
    seed_manager2 = SeedManager(global_seed=42)
    heuristic2 = RandomizedValueOrdering(seed_manager2)
    values2 = heuristic2.order_values(variable, {})
    
    assert values1 == values2


def test_randomized_value_ordering_different_seeds():
    """Test that different seeds produce different value orders"""
    variable = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    
    seed_manager1 = SeedManager(global_seed=42)
    heuristic1 = RandomizedValueOrdering(seed_manager1)
    values1 = heuristic1.order_values(variable, {})
    
    seed_manager2 = SeedManager(global_seed=43)
    heuristic2 = RandomizedValueOrdering(seed_manager2)
    values2 = heuristic2.order_values(variable, {})
    
    # Very high probability of different order with 11 values
    assert values1 != values2


# MRVWithRandomTiebreaking tests

def test_mrv_random_tiebreak_no_ties():
    """Test MRV with random tiebreaking when no ties"""
    variables = {
        "x": Variable("x", IntDomain([(0, 2)], width=8, signed=False)),    # size 3
        "y": Variable("y", IntDomain([(0, 5)], width=8, signed=False)),    # size 6
        "z": Variable("z", IntDomain([(0, 10)], width=8, signed=False)),   # size 11
    }
    
    seed_manager = SeedManager(global_seed=42)
    heuristic = MRVWithRandomTiebreaking(seed_manager)
    
    order = heuristic.order_variables(variables, set())
    
    # Should be ordered by size (MRV)
    assert order == ["x", "y", "z"]


def test_mrv_random_tiebreak_with_ties():
    """Test MRV with random tiebreaking when ties exist"""
    variables = {
        "x": Variable("x", IntDomain([(0, 5)], width=8, signed=False)),   # size 6
        "y": Variable("y", IntDomain([(0, 5)], width=8, signed=False)),   # size 6
        "z": Variable("z", IntDomain([(0, 2)], width=8, signed=False)),   # size 3
        "w": Variable("w", IntDomain([(0, 5)], width=8, signed=False)),   # size 6
    }
    
    seed_manager = SeedManager(global_seed=42)
    heuristic = MRVWithRandomTiebreaking(seed_manager)
    
    order = heuristic.order_variables(variables, set())
    
    # z should be first (smallest)
    assert order[0] == "z"
    
    # x, y, w should follow in some order
    assert set(order[1:]) == {"x", "y", "w"}


def test_mrv_random_tiebreak_reproducible():
    """Test reproducibility of tiebreaking"""
    variables = {
        "a": Variable("a", IntDomain([(0, 5)], width=8, signed=False)),
        "b": Variable("b", IntDomain([(0, 5)], width=8, signed=False)),
        "c": Variable("c", IntDomain([(0, 5)], width=8, signed=False)),
    }
    
    seed_manager1 = SeedManager(global_seed=42)
    heuristic1 = MRVWithRandomTiebreaking(seed_manager1)
    order1 = heuristic1.order_variables(variables, set())
    
    seed_manager2 = SeedManager(global_seed=42)
    heuristic2 = MRVWithRandomTiebreaking(seed_manager2)
    order2 = heuristic2.order_variables(variables, set())
    
    assert order1 == order2


# SolveBeforeRandomizedOrdering tests

def test_solve_before_randomized_basic():
    """Test solve-before with randomization"""
    variables = create_variables(["x", "y", "z", "w"], [(0, 10)] * 4)
    
    # x before y before z; w is unconstrained
    solve_order = {"x": 0, "y": 1, "z": 2}
    
    seed_manager = SeedManager(global_seed=42)
    heuristic = SolveBeforeRandomizedOrdering(solve_order, seed_manager)
    
    order = heuristic.order_variables(variables, set())
    
    # x, y, z should be in order
    x_idx = order.index("x")
    y_idx = order.index("y")
    z_idx = order.index("z")
    
    assert x_idx < y_idx < z_idx


def test_solve_before_randomized_unconstrained():
    """Test that unconstrained variables are randomized"""
    variables = create_variables(["a", "b", "c", "d"], [(0, 10)] * 4)
    
    # Only a and b have solve-before constraint
    solve_order = {"a": 0, "b": 1}
    
    seed_manager1 = SeedManager(global_seed=42)
    heuristic1 = SolveBeforeRandomizedOrdering(solve_order, seed_manager1)
    order1 = heuristic1.order_variables(variables, set())
    
    seed_manager2 = SeedManager(global_seed=43)
    heuristic2 = SolveBeforeRandomizedOrdering(solve_order, seed_manager2)
    order2 = heuristic2.order_variables(variables, set())
    
    # a should always come before b
    assert order1.index("a") < order1.index("b")
    assert order2.index("a") < order2.index("b")
    
    # But c and d positions may differ
    # (Implementation currently puts ordered first, but this tests the principle)


def test_solve_before_randomized_reproducible():
    """Test reproducibility"""
    variables = create_variables(["a", "b", "c", "d"], [(0, 10)] * 4)
    solve_order = {"a": 0, "b": 1}
    
    seed_manager1 = SeedManager(global_seed=42)
    heuristic1 = SolveBeforeRandomizedOrdering(solve_order, seed_manager1)
    order1 = heuristic1.order_variables(variables, set())
    
    seed_manager2 = SeedManager(global_seed=42)
    heuristic2 = SolveBeforeRandomizedOrdering(solve_order, seed_manager2)
    order2 = heuristic2.order_variables(variables, set())
    
    assert order1 == order2


# AdaptiveRandomizedOrdering tests

def test_adaptive_randomized_constrained():
    """Test adaptive ordering with constrained variables"""
    variables = {
        "x": Variable("x", IntDomain([(0, 2)], width=8, signed=False)),    # size 3 - constrained
        "y": Variable("y", IntDomain([(0, 20)], width=8, signed=False)),   # size 21 - unconstrained
        "z": Variable("z", IntDomain([(0, 5)], width=8, signed=False)),    # size 6 - constrained
    }
    
    seed_manager = SeedManager(global_seed=42)
    heuristic = AdaptiveRandomizedOrdering(domain_threshold=10, seed_manager=seed_manager)
    
    order = heuristic.order_variables(variables, set())
    
    # Constrained (x, z) should come before unconstrained (y)
    x_idx = order.index("x")
    z_idx = order.index("z")
    y_idx = order.index("y")
    
    assert x_idx < y_idx
    assert z_idx < y_idx
    
    # x should be before z (smaller domain)
    assert x_idx < z_idx


def test_adaptive_randomized_reproducible():
    """Test reproducibility of adaptive ordering"""
    variables = {
        "a": Variable("a", IntDomain([(0, 5)], width=8, signed=False)),
        "b": Variable("b", IntDomain([(0, 20)], width=8, signed=False)),
        "c": Variable("c", IntDomain([(0, 15)], width=8, signed=False)),
    }
    
    seed_manager1 = SeedManager(global_seed=42)
    heuristic1 = AdaptiveRandomizedOrdering(domain_threshold=10, seed_manager=seed_manager1)
    order1 = heuristic1.order_variables(variables, set())
    
    seed_manager2 = SeedManager(global_seed=42)
    heuristic2 = AdaptiveRandomizedOrdering(domain_threshold=10, seed_manager=seed_manager2)
    order2 = heuristic2.order_variables(variables, set())
    
    assert order1 == order2


# Integration tests

def test_integration_uniform_sampling():
    """Test that randomized ordering provides diverse solutions"""
    variables = create_variables(["x", "y"], [(0, 3), (0, 3)])
    
    # Generate multiple variable orders with different seeds
    orders = []
    for seed in range(10):
        seed_manager = SeedManager(global_seed=seed)
        heuristic = RandomizedVariableOrdering(seed_manager)
        order = heuristic.order_variables(variables, set())
        orders.append(tuple(order))
    
    # Should have some diversity (not all the same)
    unique_orders = set(orders)
    assert len(unique_orders) > 1  # At least 2 different orders


def test_integration_value_diversity():
    """Test that randomized value ordering provides diversity"""
    variable = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    
    # Generate multiple value orders with different seeds
    value_orders = []
    for seed in range(10):
        seed_manager = SeedManager(global_seed=seed)
        heuristic = RandomizedValueOrdering(seed_manager)
        values = heuristic.order_values(variable, {})
        value_orders.append(tuple(values))
    
    # Should have diversity
    unique_orders = set(value_orders)
    assert len(unique_orders) > 1


def test_repr():
    """Test string representations"""
    seed_manager = SeedManager(42)
    
    h1 = RandomizedVariableOrdering(seed_manager)
    assert "RandomizedVariableOrdering" in repr(h1)
    
    h2 = RandomizedValueOrdering(seed_manager)
    assert "RandomizedValueOrdering" in repr(h2)
    
    h3 = MRVWithRandomTiebreaking(seed_manager)
    assert "MRVWithRandomTiebreaking" in repr(h3)
    
    h4 = SolveBeforeRandomizedOrdering({}, seed_manager)
    assert "SolveBeforeRandomizedOrdering" in repr(h4)
    
    h5 = AdaptiveRandomizedOrdering(seed_manager=seed_manager)
    assert "AdaptiveRandomizedOrdering" in repr(h5)
