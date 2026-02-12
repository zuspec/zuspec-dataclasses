"""Tests for preprocessing pipeline."""

import pytest
from zuspec.dataclasses.solver.preprocessing import (
    ConstantFolder,
    RangeAnalyzer,
    DependencyAnalyzer,
    AlgebraicSimplifier,
    PreprocessingPipeline,
)
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.core.constraint import Constraint


def test_range_analyzer_basic():
    """Test basic range analyzer initialization and analysis."""
    analyzer = RangeAnalyzer(bit_width=32)
    
    x_var = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    y_var = Variable("y", domain=IntDomain([(5, 15)], width=32, signed=False))
    variables = {"x": x_var, "y": y_var}
    
    ranges = analyzer.analyze(variables)
    
    assert "x" in ranges
    assert "y" in ranges
    assert ranges["x"] == (0, 10)
    assert ranges["y"] == (5, 15)


def test_range_analyzer_unsat_detection():
    """Test UNSAT detection when domains are empty."""
    analyzer = RangeAnalyzer(bit_width=32)
    
    # Manually set impossible range
    analyzer.ranges = {"x": (10, 5)}  # min > max
    
    assert analyzer.detect_unsat()


def test_dependency_analyzer_basic():
    """Test basic dependency analysis."""
    analyzer = DependencyAnalyzer()
    
    x_var = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    y_var = Variable("y", domain=IntDomain([(0, 10)], width=32, signed=False))
    variables = {"x": x_var, "y": y_var}
    
    # Create mock constraints (these would normally be parsed from PSS)
    constraints = [
        Constraint(variables={x_var}),
        Constraint(variables={y_var}),
    ]
    
    analyzer.analyze(constraints, variables)
    components = analyzer.get_components()
    
    # Should have 2 independent components (no shared variables)
    assert len(components) == 2


def test_dependency_analyzer_shared_variable():
    """Test that constraints sharing a variable are in same component."""
    analyzer = DependencyAnalyzer()
    
    x_var = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    y_var = Variable("y", domain=IntDomain([(0, 10)], width=32, signed=False))
    variables = {"x": x_var, "y": y_var}
    
    # Both constraints involve x
    constraints = [
        Constraint(variables={x_var}),
        Constraint(variables={x_var, y_var}),
    ]
    
    analyzer.analyze(constraints, variables)
    components = analyzer.get_components()
    
    # Should have 1 component containing both constraints
    assert len(components) == 1
    assert len(components[0]) == 2


def test_preprocessing_pipeline_basic():
    """Test basic preprocessing pipeline."""
    from zuspec.dataclasses.solver.core.constraint_system import ConstraintSystem
    
    system = ConstraintSystem()
    system.variables = {
        "x": Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False)),
        "y": Variable("y", domain=IntDomain([(0, 10)], width=32, signed=False)),
    }
    
    x_var = system.variables["x"]
    system.constraints = [
        Constraint(variables={x_var}),
    ]
    
    pipeline = PreprocessingPipeline(bit_width=32)
    results = pipeline.preprocess(system)
    
    assert not results['unsat']
    assert 'components' in results
    assert 'ordering' in results


def test_constant_folder_passthrough():
    """Test that constant folder passes through constraints."""
    folder = ConstantFolder()
    
    x_var = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    constraints = [
        Constraint(variables={x_var}),
    ]
    
    result = folder.fold_constraints(constraints)
    
    assert len(result) == len(constraints)


def test_algebraic_simplifier_passthrough():
    """Test that algebraic simplifier passes through constraints."""
    simplifier = AlgebraicSimplifier()
    
    x_var = Variable("x", domain=IntDomain([(0, 10)], width=32, signed=False))
    constraints = [
        Constraint(variables={x_var}),
    ]
    
    result = simplifier.simplify_constraints(constraints)
    
    assert len(result) == len(constraints)
