"""Tests for foreach constraint expansion and soft constraints"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.propagators.foreach import (
    ForeachExpander,
    ForeachConstraintGroup,
    create_unique_array_foreach,
)
from zuspec.dataclasses.solver.propagators.relational import GreaterThanPropagator
from zuspec.dataclasses.solver.propagators.uniqueness import PairwiseUniquePropagator
from zuspec.dataclasses.solver.soft_constraints import (
    SoftConstraint,
    SoftConstraintManager,
)


# Foreach tests

def test_foreach_expander_basic():
    """Test basic foreach expansion"""
    array_vars = ["arr_0", "arr_1", "arr_2"]
    
    def generator(i, var_name):
        # arr[i] > 0
        return GreaterThanPropagator(var_name, IntDomain([(0, 0)], width=8, signed=False))
    
    props = ForeachExpander.expand_foreach(array_vars, generator)
    
    assert len(props) == 3
    assert all(isinstance(p, GreaterThanPropagator) for p in props)


def test_foreach_expander_with_skip():
    """Test foreach expansion with conditional skip"""
    array_vars = ["arr_0", "arr_1", "arr_2", "arr_3"]
    
    def generator(i, var_name):
        # Only apply constraint if i < 3
        if i < 3:
            return GreaterThanPropagator(var_name, IntDomain([(0, 0)], width=8, signed=False))
        return None
    
    props = ForeachExpander.expand_foreach(array_vars, generator)
    
    assert len(props) == 3  # Only first 3


def test_foreach_expander_nested():
    """Test nested foreach expansion"""
    outer = ["a_0", "a_1"]
    inner = ["b_0", "b_1", "b_2"]
    
    generated = []
    
    def generator(i, outer_var, j, inner_var):
        generated.append((i, outer_var, j, inner_var))
        return PairwiseUniquePropagator(outer_var, inner_var)
    
    props = ForeachExpander.expand_nested_foreach(outer, inner, generator)
    
    # Should generate 2 * 3 = 6 constraints
    assert len(props) == 6
    assert len(generated) == 6
    
    # Check all combinations
    expected = [
        (0, "a_0", 0, "b_0"),
        (0, "a_0", 1, "b_1"),
        (0, "a_0", 2, "b_2"),
        (1, "a_1", 0, "b_0"),
        (1, "a_1", 1, "b_1"),
        (1, "a_1", 2, "b_2"),
    ]
    assert generated == expected


def test_foreach_constraint_group_propagate():
    """Test ForeachConstraintGroup propagation"""
    # Create variables
    arr = [Variable(f"arr_{i}", IntDomain([(0, 10)], width=8, signed=False)) for i in range(3)]
    zero = Variable("zero", IntDomain([(0, 0)], width=8, signed=False))
    variables = {f"arr_{i}": arr[i] for i in range(3)}
    variables["zero"] = zero
    
    # Create foreach group: all arr[i] > 0
    def generator(i, var_name):
        return GreaterThanPropagator(var_name, "zero")
    
    props = ForeachExpander.expand_foreach([f"arr_{i}" for i in range(3)], generator)
    group = ForeachConstraintGroup(props, name="arr_positive")
    
    result = group.propagate(variables)
    
    # All array elements should have 0 removed
    assert not result.is_conflict()
    for i in range(3):
        assert 0 not in list(arr[i].domain.values())


def test_foreach_constraint_group_conflict():
    """Test ForeachConstraintGroup conflict detection"""
    # arr[i] can only be [0, 0], but constraint is arr[i] > 5
    arr = [Variable(f"arr_{i}", IntDomain([(0, 0)], width=8, signed=False)) for i in range(2)]
    bound = Variable("bound", IntDomain([(5, 5)], width=8, signed=False))
    variables = {f"arr_{i}": arr[i] for i in range(2)}
    variables["bound"] = bound
    
    def generator(i, var_name):
        return GreaterThanPropagator(var_name, "bound")
    
    props = ForeachExpander.expand_foreach([f"arr_{i}" for i in range(2)], generator)
    group = ForeachConstraintGroup(props)
    
    result = group.propagate(variables)
    
    # Should detect conflict
    assert result.is_conflict()


def test_foreach_constraint_group_affected_variables():
    """Test affected_variables for foreach group"""
    def generator(i, var_name):
        return GreaterThanPropagator(var_name, "zero")
    
    props = ForeachExpander.expand_foreach(["arr_0", "arr_1"], generator)
    group = ForeachConstraintGroup(props)
    
    affected = group.affected_variables()
    assert "arr_0" in affected
    assert "arr_1" in affected
    assert "zero" in affected


def test_create_unique_array_foreach():
    """Test helper for unique array constraints"""
    array_vars = ["arr_0", "arr_1", "arr_2"]
    group = create_unique_array_foreach(array_vars)
    
    # Should create pairwise uniqueness constraints
    # For 3 elements: (0,1), (0,2), (1,2) = 3 constraints
    assert len(group.propagators) == 3


# Soft constraint tests

def test_soft_constraint_basic():
    """Test basic soft constraint creation"""
    prop = GreaterThanPropagator("x", IntDomain([(5, 5)], width=8, signed=False))
    soft = SoftConstraint(prop, weight=10, name="prefer_x_large")
    
    assert soft.weight == 10
    assert soft.name == "prefer_x_large"


def test_soft_constraint_is_satisfied():
    """Test soft constraint satisfaction check"""
    # Create constant for comparison
    bound = Variable("bound", IntDomain([(5, 5)], width=8, signed=False))
    prop = GreaterThanPropagator("x", "bound")
    soft = SoftConstraint(prop, weight=1)
    
    # x = 10 > bound = 5, should be satisfied
    assignment = {"x": 10, "bound": 5}
    assert soft.is_satisfied(assignment)


def test_soft_constraint_manager_add():
    """Test adding soft constraints"""
    manager = SoftConstraintManager()
    
    prop1 = GreaterThanPropagator("x", IntDomain([(5, 5)], width=8, signed=False))
    prop2 = GreaterThanPropagator("y", IntDomain([(10, 10)], width=8, signed=False))
    
    manager.add_soft_constraint(prop1, weight=5)
    manager.add_soft_constraint(prop2, weight=10)
    
    assert len(manager.soft_constraints) == 2


def test_soft_constraint_manager_score():
    """Test solution scoring"""
    manager = SoftConstraintManager()
    
    # Add soft constraints with mock propagators
    class MockProp:
        def __init__(self, should_satisfy):
            self.should_satisfy = should_satisfy
        
        def is_satisfied(self, assignment):
            return self.should_satisfy
        
        def affected_variables(self):
            return set()
    
    manager.add_soft_constraint(MockProp(True), weight=10)
    manager.add_soft_constraint(MockProp(True), weight=5)
    manager.add_soft_constraint(MockProp(False), weight=3)
    
    score = manager.score_solution({})
    
    # Score = 10 + 5 = 15 (third not satisfied)
    assert score == 15


def test_soft_constraint_manager_violated():
    """Test getting violated constraints"""
    manager = SoftConstraintManager()
    
    class MockProp:
        def __init__(self, should_satisfy, name):
            self.should_satisfy = should_satisfy
            self.name = name
        
        def is_satisfied(self, assignment):
            return self.should_satisfy
        
        def affected_variables(self):
            return set()
    
    manager.add_soft_constraint(MockProp(True, "c1"), weight=10, name="satisfied")
    manager.add_soft_constraint(MockProp(False, "c2"), weight=5, name="violated1")
    manager.add_soft_constraint(MockProp(False, "c3"), weight=3, name="violated2")
    
    violated = manager.get_violated_constraints({})
    
    assert len(violated) == 2
    assert all(v.name in ["violated1", "violated2"] for v in violated)


def test_soft_constraint_manager_summary():
    """Test getting satisfaction summary"""
    manager = SoftConstraintManager()
    
    class MockProp:
        def __init__(self, should_satisfy):
            self.should_satisfy = should_satisfy
        
        def is_satisfied(self, assignment):
            return self.should_satisfy
        
        def affected_variables(self):
            return set()
    
    manager.add_soft_constraint(MockProp(True), weight=10)
    manager.add_soft_constraint(MockProp(True), weight=5)
    manager.add_soft_constraint(MockProp(False), weight=3)
    
    summary = manager.get_satisfaction_summary({})
    
    assert summary['score'] == 15
    assert summary['max_score'] == 18
    assert summary['satisfied_count'] == 2
    assert summary['violated_count'] == 1
    assert abs(summary['satisfaction_rate'] - (15/18)) < 0.01


def test_soft_constraint_manager_compare():
    """Test comparing two solutions"""
    manager = SoftConstraintManager()
    
    class MockProp:
        def __init__(self, var_name, threshold):
            self.var_name = var_name
            self.threshold = threshold
        
        def is_satisfied(self, assignment):
            return assignment.get(self.var_name, 0) > self.threshold
        
        def affected_variables(self):
            return {self.var_name}
    
    manager.add_soft_constraint(MockProp("x", 5), weight=10)
    manager.add_soft_constraint(MockProp("y", 3), weight=5)
    
    sol1 = {"x": 10, "y": 5}  # Both satisfied, score = 15
    sol2 = {"x": 10, "y": 2}  # Only x satisfied, score = 10
    sol3 = {"x": 3, "y": 2}   # Neither satisfied, score = 0
    
    assert manager.compare_solutions(sol1, sol2) == 1  # sol1 better
    assert manager.compare_solutions(sol2, sol1) == -1  # sol2 worse
    assert manager.compare_solutions(sol2, sol3) == 1  # sol2 better
    assert manager.compare_solutions(sol1, sol1) == 0  # equal


def test_soft_constraint_repr():
    """Test string representation"""
    prop = GreaterThanPropagator("x", "bound")
    soft = SoftConstraint(prop, weight=10, name="test")
    
    repr_str = repr(soft)
    assert "SoftConstraint" in repr_str
    assert "weight=10" in repr_str


def test_foreach_repr():
    """Test foreach group string representation"""
    def generator(i, var_name):
        return GreaterThanPropagator(var_name, IntDomain([(0, 0)], width=8, signed=False))
    
    props = ForeachExpander.expand_foreach(["a", "b"], generator)
    group = ForeachConstraintGroup(props, name="test_group")
    
    repr_str = repr(group)
    assert "ForeachConstraintGroup" in repr_str
    assert "test_group" in repr_str
    assert "2 constraints" in repr_str
