"""Tests for backtracking search."""

import pytest
from zuspec.dataclasses.solver.engine import (
    BacktrackingSearch,
    PropagationEngine,
    MinimumRemainingValues,
    MostConstrainedVariable,
    MRVWithTiebreaking,
    RandomValueOrdering,
    InOrderValueOrdering,
    SolveBeforeOrderingHeuristic,
)
from zuspec.dataclasses.solver.propagators import (
    AddPropagator,
    EqualPropagator,
    LessThanPropagator,
)
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain


def test_backtracking_search_simple():
    """Test basic backtracking search with simple constraint."""
    x = Variable("x", domain=IntDomain([(0, 5)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(0, 5)], width=32, signed=False))
    
    variables = {"x": x, "y": y}
    
    # Constraint: x == y
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(EqualPropagator("x", "y"))
    
    search = BacktrackingSearch(engine)
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["x"] == solution["y"]
    assert 0 <= solution["x"] <= 5


def test_backtracking_search_addition():
    """Test search with addition constraint."""
    x = Variable("x", domain=IntDomain([(0, 5)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(0, 5)], width=32, signed=False))
    z = Variable("z", domain=IntDomain([(7, 7)], width=32, signed=False))  # Singleton
    
    variables = {"x": x, "y": y, "z": z}
    
    # Constraint: z = x + y, where z = 7
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(AddPropagator("z", "x", "y", bit_width=32))
    
    search = BacktrackingSearch(engine)
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["x"] + solution["y"] == 7


def test_backtracking_search_unsatisfiable():
    """Test search with unsatisfiable constraints."""
    x = Variable("x", domain=IntDomain([(0, 5)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(10, 15)], width=32, signed=False))
    
    variables = {"x": x, "y": y}
    
    # Constraint: x == y (impossible)
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(EqualPropagator("x", "y"))
    
    search = BacktrackingSearch(engine)
    solution = search.solve(variables)
    
    assert solution is None


def test_backtracking_search_less_than():
    """Test search with inequality constraint."""
    x = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(0, 10)], width=32, signed=False))
    
    variables = {"x": x, "y": y}
    
    # Constraint: x < y
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(LessThanPropagator("x", "y"))
    
    search = BacktrackingSearch(engine)
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["x"] < solution["y"]


def test_mrv_heuristic():
    """Test Minimum Remaining Values heuristic."""
    x = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(0, 2)], width=32, signed=False))  # Smaller domain
    
    variables = {"x": x, "y": y}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(LessThanPropagator("y", "x"))
    
    heuristic = MinimumRemainingValues()
    search = BacktrackingSearch(engine, var_heuristic=heuristic)
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["y"] < solution["x"]


def test_mrv_with_tiebreaking():
    """Test MRV with most-constrained tiebreaking."""
    x = Variable("x", domain=IntDomain([(0, 5)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(0, 5)], width=32, signed=False))
    z = Variable("z", domain=IntDomain([(0, 5)], width=32, signed=False))
    
    variables = {"x": x, "y": y, "z": z}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    # y is in more constraints
    engine.add_propagator(EqualPropagator("x", "y"))
    engine.add_propagator(LessThanPropagator("y", "z"))
    
    heuristic = MRVWithTiebreaking()
    search = BacktrackingSearch(engine, var_heuristic=heuristic)
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["x"] == solution["y"]
    assert solution["y"] < solution["z"]


def test_random_value_ordering():
    """Test random value ordering with seed."""
    x = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    
    variables = {"x": x}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    
    # Use fixed seed for determinism
    val_heuristic = RandomValueOrdering(seed=42)
    search = BacktrackingSearch(engine, val_heuristic=val_heuristic)
    solution = search.solve(variables)
    
    assert solution is not None
    assert 0 <= solution["x"] <= 10


def test_in_order_value_ordering():
    """Test in-order value ordering."""
    x = Variable("x", domain=IntDomain([(5, 10)], width=32, signed=False))
    
    variables = {"x": x}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    
    val_heuristic = InOrderValueOrdering()
    search = BacktrackingSearch(engine, val_heuristic=val_heuristic)
    solution = search.solve(variables)
    
    assert solution is not None
    # Should pick first value (5) with in-order heuristic
    assert solution["x"] == 5


def test_solve_before_ordering():
    """Test solve...before ordering heuristic."""
    x = Variable("x", domain=IntDomain([(0, 5)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(0, 5)], width=32, signed=False))
    z = Variable("z", domain=IntDomain([(0, 5)], width=32, signed=False))
    
    variables = {"x": x, "y": y, "z": z}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(LessThanPropagator("x", "y"))
    engine.add_propagator(LessThanPropagator("y", "z"))
    
    # Specify ordering: solve x before y before z
    solve_before = [("x", "y"), ("y", "z")]
    heuristic = SolveBeforeOrderingHeuristic(solve_before)
    
    search = BacktrackingSearch(engine, var_heuristic=heuristic)
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["x"] < solution["y"] < solution["z"]


def test_search_statistics():
    """Test that search statistics are tracked."""
    x = Variable("x", domain=IntDomain([(0, 5)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(0, 5)], width=32, signed=False))
    
    variables = {"x": x, "y": y}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(EqualPropagator("x", "y"))
    
    search = BacktrackingSearch(engine)
    solution = search.solve(variables)
    
    stats = search.get_statistics()
    assert stats['nodes_explored'] > 0
    assert stats['backtracks'] >= 0


def test_backtrack_limit():
    """Test that search respects backtrack limit."""
    x = Variable("x", domain=IntDomain([(0, 100)], width=32, signed=False))
    y = Variable("y", domain=IntDomain([(0, 100)], width=32, signed=False))
    z = Variable("z", domain=IntDomain([(150, 150)], width=32, signed=False))
    
    variables = {"x": x, "y": y, "z": z}
    
    # Constraint: z = x + y where z = 150
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(AddPropagator("z", "x", "y", bit_width=32))
    
    # Set very low backtrack limit
    search = BacktrackingSearch(engine, max_backtracks=5)
    solution = search.solve(variables)
    
    # May or may not find solution with low limit
    # Just verify it doesn't hang
    if solution:
        assert solution["x"] + solution["y"] == 150


def test_complex_constraint_system():
    """Test search with multiple constraints."""
    a = Variable("a", domain=IntDomain([(1, 5)], width=32, signed=False))
    b = Variable("b", domain=IntDomain([(1, 5)], width=32, signed=False))
    c = Variable("c", domain=IntDomain([(1, 10)], width=32, signed=False))
    
    variables = {"a": a, "b": b, "c": c}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    
    # Constraints: a < b, c = a + b
    engine.add_propagator(LessThanPropagator("a", "b"))
    engine.add_propagator(AddPropagator("c", "a", "b", bit_width=32))
    
    search = BacktrackingSearch(engine)
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["a"] < solution["b"]
    assert solution["c"] == solution["a"] + solution["b"]
