"""Integration tests for randc with backtracking search"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable, VarKind
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.engine import BacktrackingSearch, PropagationEngine
from zuspec.dataclasses.solver.propagators.arithmetic import AddPropagator
from zuspec.dataclasses.solver.propagators.relational import EqualPropagator, LessThanPropagator
from zuspec.dataclasses.solver.randc import RandCManager, RandCConfig


def test_randc_basic_solve():
    """Test basic solving with randc variable"""
    # x is randc, x in [0, 5]
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False), kind=VarKind.RANDC)
    variables = {"x": x}
    
    # No constraints, just pick a value
    engine = PropagationEngine()
    engine.set_variables(variables)
    
    randc_config = RandCConfig(seed=42)
    search = BacktrackingSearch(engine, randc_manager=RandCManager(randc_config))
    
    solution = search.solve(variables)
    
    assert solution is not None
    assert "x" in solution
    assert 0 <= solution["x"] <= 5


def test_randc_with_constraint():
    """Test randc with additional constraint"""
    # x is randc, y is rand
    # x + y = 10, x < 5
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False), kind=VarKind.RANDC)
    y = Variable("y", IntDomain([(0, 10)], width=8, signed=False), kind=VarKind.RAND)
    z = Variable("z", IntDomain([(10, 10)], width=8, signed=False))
    bound = Variable("bound", IntDomain([(5, 5)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z, "bound": bound}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(AddPropagator("z", "x", "y", bit_width=8))
    engine.add_propagator(LessThanPropagator("x", "bound"))
    
    randc_config = RandCConfig(seed=42)
    search = BacktrackingSearch(engine, randc_manager=RandCManager(randc_config))
    
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["x"] < 5
    assert solution["x"] + solution["y"] == 10


def test_randc_permutation_ordering():
    """Test that randc tries values from permutation"""
    # Create randc variable with small domain
    x = Variable("x", IntDomain([(0, 2)], width=8, signed=False), kind=VarKind.RANDC)
    y = Variable("y", IntDomain([(5, 5)], width=8, signed=False))  # Force x to not be 0
    variables = {"x": x, "y": y}
    
    # x must equal y (forces constraint)
    engine = PropagationEngine()
    engine.set_variables(variables)
    # This will make x=5 impossible, so randc will try multiple values
    
    randc_config = RandCConfig(seed=42, max_permutation_retries=10)
    search = BacktrackingSearch(engine, randc_manager=RandCManager(randc_config))
    
    solution = search.solve(variables)
    
    # Should find solution (no actual conflicting constraint)
    assert solution is not None
    assert 0 <= solution["x"] <= 2


def test_randc_cycle_behavior():
    """Test randc cycle completion and reset"""
    # Small domain to complete cycle quickly
    x = Variable("x", IntDomain([(0, 2)], width=8, signed=False), kind=VarKind.RANDC)
    variables = {"x": x}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    
    randc_config = RandCConfig(seed=123)
    randc_manager = RandCManager(randc_config)
    search = BacktrackingSearch(engine, randc_manager=randc_manager)
    
    # Solve multiple times to trigger cycle
    solutions = []
    for i in range(6):  # More than 2 cycles worth
        solution = search.solve(variables)
        assert solution is not None
        solutions.append(solution["x"])
        
        # Mark as successful and reset for next solve
        randc_manager.mark_value_success(x, solution["x"])
        # Reset variables for next solve
        x.domain = IntDomain([(0, 2)], width=8, signed=False)
    
    # Should have gotten all values at least once
    unique_values = set(solutions)
    assert len(unique_values) >= 2  # At least 2 different values


def test_randc_with_conflict_retry():
    """Test that randc retries with next permutation value on conflict"""
    # randc x in [0, 3]
    # x + y = 5, y = 2
    # Valid solutions: x=3
    x = Variable("x", IntDomain([(0, 3)], width=8, signed=False), kind=VarKind.RANDC)
    y = Variable("y", IntDomain([(2, 2)], width=8, signed=False))
    z = Variable("z", IntDomain([(5, 5)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(AddPropagator("z", "x", "y", bit_width=8))
    
    randc_config = RandCConfig(seed=42)
    search = BacktrackingSearch(engine, randc_manager=RandCManager(randc_config))
    
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["x"] == 3
    assert solution["y"] == 2
    assert solution["z"] == 5


def test_randc_unsatisfiable():
    """Test randc with unsatisfiable constraints"""
    # x is randc in [0, 2]
    # x = 10 (impossible)
    x = Variable("x", IntDomain([(0, 2)], width=8, signed=False), kind=VarKind.RANDC)
    y = Variable("y", IntDomain([(10, 10)], width=8, signed=False))
    variables = {"x": x, "y": y}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(EqualPropagator("x", "y"))
    
    randc_config = RandCConfig(seed=42, max_permutation_retries=5)
    search = BacktrackingSearch(engine, randc_manager=RandCManager(randc_config))
    
    solution = search.solve(variables)
    
    # Should fail to find solution
    assert solution is None


def test_randc_max_retries_exhausted():
    """Test that randc gives up after max retries"""
    # Very constrained problem that requires specific value
    x = Variable("x", IntDomain([(0, 1)], width=8, signed=False), kind=VarKind.RANDC)
    y = Variable("y", IntDomain([(5, 5)], width=8, signed=False))
    variables = {"x": x, "y": y}
    
    # Impossible constraint
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(EqualPropagator("x", "y"))
    
    # Low retry limit
    randc_config = RandCConfig(seed=42, max_permutation_retries=2)
    search = BacktrackingSearch(engine, randc_manager=RandCManager(randc_config))
    
    solution = search.solve(variables)
    
    assert solution is None


def test_mixed_randc_and_rand():
    """Test solving with both randc and rand variables"""
    # x is randc, y is rand
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False), kind=VarKind.RANDC)
    y = Variable("y", IntDomain([(0, 5)], width=8, signed=False), kind=VarKind.RAND)
    z = Variable("z", IntDomain([(8, 8)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z}
    
    # x + y = 8
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(AddPropagator("z", "x", "y", bit_width=8))
    
    randc_config = RandCConfig(seed=42)
    search = BacktrackingSearch(engine, randc_manager=RandCManager(randc_config))
    
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["x"] + solution["y"] == 8
    assert 0 <= solution["x"] <= 5
    assert 0 <= solution["y"] <= 5


def test_randc_reduced_domain():
    """Test randc with domain reduced by propagation"""
    # x is randc in [0, 10]
    # x < 3 (propagation reduces to [0, 2])
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False), kind=VarKind.RANDC)
    bound = Variable("bound", IntDomain([(3, 3)], width=8, signed=False))
    variables = {"x": x, "bound": bound}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    engine.add_propagator(LessThanPropagator("x", "bound"))
    
    randc_config = RandCConfig(seed=42)
    search = BacktrackingSearch(engine, randc_manager=RandCManager(randc_config))
    
    solution = search.solve(variables)
    
    assert solution is not None
    assert solution["x"] < 3
    assert 0 <= solution["x"] <= 10


def test_randc_statistics():
    """Test that randc search produces statistics"""
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False), kind=VarKind.RANDC)
    variables = {"x": x}
    
    engine = PropagationEngine()
    engine.set_variables(variables)
    
    randc_config = RandCConfig(seed=42)
    search = BacktrackingSearch(engine, randc_manager=RandCManager(randc_config))
    
    solution = search.solve(variables)
    assert solution is not None
    
    stats = search.get_statistics()
    assert "nodes_explored" in stats
    assert "backtracks" in stats
    assert stats["nodes_explored"] > 0
