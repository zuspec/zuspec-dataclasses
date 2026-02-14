"""Tests for solution generation and validation"""

import pytest
from zuspec.dataclasses.solver.solution import (
    Solution, SolutionStatus, SolutionGenerator
)
from zuspec.dataclasses.solver.core.variable import Variable, VarKind
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.propagators.arithmetic import AddPropagator
from zuspec.dataclasses.solver.propagators.relational import EqualPropagator


def test_solution_creation():
    """Test creating a solution"""
    generator = SolutionGenerator()
    
    solution = generator.create_solution(
        status=SolutionStatus.SATISFIABLE,
        assignments={"x": 5, "y": 10},
        statistics={"nodes": 42}
    )
    
    assert solution.is_satisfiable()
    assert solution.get_value("x") == 5
    assert solution.get_value("y") == 10
    assert solution.statistics["nodes"] == 42


def test_unsat_solution():
    """Test creating UNSAT solution"""
    generator = SolutionGenerator()
    
    solution = generator.create_solution(
        status=SolutionStatus.UNSATISFIABLE,
        errors=["Domain empty for x"]
    )
    
    assert not solution.is_satisfiable()
    assert len(solution.errors) == 1
    assert "Domain empty" in solution.errors[0]


def test_solution_validation_success():
    """Test validating a correct solution"""
    generator = SolutionGenerator()
    
    # Create variables: x + y = 10, x = y
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    y = Variable("y", IntDomain([(0, 10)], width=8, signed=False))
    z = Variable("z", IntDomain([(10, 10)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z}
    
    # Create propagators
    add_prop = AddPropagator("z", "x", "y", bit_width=8)
    eq_prop = EqualPropagator("x", "y")
    propagators = [add_prop, eq_prop]
    
    # Valid solution: x=5, y=5, z=10
    solution = generator.create_solution(
        status=SolutionStatus.SATISFIABLE,
        assignments={"x": 5, "y": 5, "z": 10}
    )
    
    is_valid = generator.validate_solution(solution, variables, propagators)
    assert is_valid


def test_solution_validation_incomplete():
    """Test validation fails for incomplete assignment"""
    generator = SolutionGenerator()
    
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    y = Variable("y", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x, "y": y}
    
    # Missing y assignment
    solution = generator.create_solution(
        status=SolutionStatus.SATISFIABLE,
        assignments={"x": 5}
    )
    
    is_valid = generator.validate_solution(solution, variables, [])
    assert not is_valid
    assert any("not assigned" in err for err in solution.errors)


def test_solution_validation_out_of_domain():
    """Test validation fails for value outside domain"""
    generator = SolutionGenerator()
    
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False))
    variables = {"x": x}
    
    # Value 10 not in domain [0, 5]
    solution = generator.create_solution(
        status=SolutionStatus.SATISFIABLE,
        assignments={"x": 10}
    )
    
    is_valid = generator.validate_solution(solution, variables, [])
    assert not is_valid
    assert any("not in domain" in err for err in solution.errors)


def test_solution_validation_constraint_violation():
    """Test validation detects constraint violations"""
    generator = SolutionGenerator()
    
    # x + y = z, but z=10
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    y = Variable("y", IntDomain([(0, 10)], width=8, signed=False))
    z = Variable("z", IntDomain([(10, 10)], width=8, signed=False))
    variables = {"x": x, "y": y, "z": z}
    
    add_prop = AddPropagator("z", "x", "y", bit_width=8)
    propagators = [add_prop]
    
    # Invalid: 3 + 3 != 10
    solution = generator.create_solution(
        status=SolutionStatus.SATISFIABLE,
        assignments={"x": 3, "y": 3, "z": 10}
    )
    
    is_valid = generator.validate_solution(solution, variables, propagators)
    assert not is_valid
    assert any("Constraint violated" in err for err in solution.errors)


def test_unsat_report_generation():
    """Test generating UNSAT report"""
    generator = SolutionGenerator()
    
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False))
    y = Variable("y", IntDomain([(10, 15)], width=8, signed=False))
    variables = {"x": x, "y": y}
    
    solution = generator.create_solution(
        status=SolutionStatus.UNSATISFIABLE,
        errors=["No common values", "Constraints conflict"],
        statistics={"backtracks": 100}
    )
    
    report = generator.format_unsat_report(solution, variables)
    
    assert "UNSATISFIABLE" in report
    assert "No common values" in report
    assert "Constraints conflict" in report
    assert "backtracks: 100" in report
    assert "x:" in report
    assert "y:" in report


def test_solution_repr():
    """Test solution string representation"""
    solution = Solution(
        status=SolutionStatus.SATISFIABLE,
        assignments={"x": 5, "y": 10},
        errors=[],
        statistics={}
    )
    
    repr_str = repr(solution)
    assert "SAT" in repr_str
    assert "x=5" in repr_str
    assert "y=10" in repr_str


def test_unsat_solution_repr():
    """Test UNSAT solution representation"""
    solution = Solution(
        status=SolutionStatus.UNSATISFIABLE,
        assignments={},
        errors=["conflict"],
        statistics={}
    )
    
    repr_str = repr(solution)
    assert "UNSATISFIABLE" in repr_str


def test_timeout_solution():
    """Test timeout solution status"""
    generator = SolutionGenerator()
    
    solution = generator.create_solution(
        status=SolutionStatus.TIMEOUT,
        errors=["Search exceeded time limit"]
    )
    
    assert not solution.is_satisfiable()
    assert solution.status == SolutionStatus.TIMEOUT


def test_error_solution():
    """Test error solution status"""
    generator = SolutionGenerator()
    
    solution = generator.create_solution(
        status=SolutionStatus.ERROR,
        errors=["Internal solver error"]
    )
    
    assert not solution.is_satisfiable()
    assert solution.status == SolutionStatus.ERROR


def test_get_value_nonexistent():
    """Test getting value for nonexistent variable"""
    solution = Solution(
        status=SolutionStatus.SATISFIABLE,
        assignments={"x": 5},
        errors=[],
        statistics={}
    )
    
    assert solution.get_value("y") is None


def test_validate_unknown_variable():
    """Test validation with unknown variable in solution"""
    generator = SolutionGenerator()
    
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    variables = {"x": x}
    
    # Solution has unknown variable
    solution = generator.create_solution(
        status=SolutionStatus.SATISFIABLE,
        assignments={"x": 5, "z": 10}
    )
    
    is_valid = generator.validate_solution(solution, variables, [])
    assert not is_valid
    assert any("Unknown variable" in err for err in solution.errors)


def test_solution_with_randc():
    """Test solution with randc variables"""
    generator = SolutionGenerator()
    
    x = Variable("x", IntDomain([(0, 5)], width=8, signed=False), kind=VarKind.RANDC)
    variables = {"x": x}
    
    solution = generator.create_solution(
        status=SolutionStatus.SATISFIABLE,
        assignments={"x": 3}
    )
    
    is_valid = generator.validate_solution(solution, variables, [])
    assert is_valid
