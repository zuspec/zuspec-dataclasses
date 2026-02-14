"""Tests for conditional constraints and ternary expressions"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.propagators.conditional import (
    ConditionalConstraint,
    TernaryExpressionPropagator,
)
from zuspec.dataclasses.solver.propagators.relational import (
    LessThanPropagator,
    GreaterEqualPropagator,
)
from zuspec.dataclasses.solver.propagators.set_membership import RangeConstraintPropagator


def test_conditional_constraint_condition_true():
    """Test conditional activates then branch when condition is true"""
    # if (mode == 1) addr < 100
    mode = Variable("mode", IntDomain([(1, 1)], width=2, signed=False))
    mode.current_value = 1
    addr = Variable("addr", IntDomain([(0, 200)], width=16, signed=False))
    bound = Variable("bound", IntDomain([(100, 100)], width=16, signed=False))
    variables = {"mode": mode, "addr": addr, "bound": bound}
    
    def evaluator(vars):
        m = vars["mode"]
        values = list(m.domain.values())
        if len(values) == 1:
            return values[0] == 1
        return None
    
    then_props = [LessThanPropagator("addr", "bound")]
    
    cond = ConditionalConstraint(
        evaluator,
        {"mode"},
        then_props,
        []
    )
    
    result = cond.propagate(variables)
    
    # addr should be restricted to [0, 99]
    assert not result.is_conflict()
    assert max(addr.domain.values()) < 100


def test_conditional_constraint_condition_false():
    """Test conditional activates else branch when condition is false"""
    # if (mode == 1) ... else addr >= 100
    mode = Variable("mode", IntDomain([(0, 0)], width=2, signed=False))
    mode.current_value = 0
    addr = Variable("addr", IntDomain([(0, 200)], width=16, signed=False))
    bound = Variable("bound", IntDomain([(100, 100)], width=16, signed=False))
    variables = {"mode": mode, "addr": addr, "bound": bound}
    
    def evaluator(vars):
        m = vars["mode"]
        values = list(m.domain.values())
        if len(values) == 1:
            return values[0] == 1
        return None
    
    then_props = []
    else_props = [GreaterEqualPropagator("addr", "bound")]
    
    cond = ConditionalConstraint(
        evaluator,
        {"mode"},
        then_props,
        else_props
    )
    
    result = cond.propagate(variables)
    
    # addr should be restricted to [100, 200]
    assert not result.is_conflict()
    assert min(addr.domain.values()) >= 100


def test_conditional_constraint_undetermined():
    """Test conditional waits when condition is undetermined"""
    # mode can be 0 or 1
    mode = Variable("mode", IntDomain([(0, 1)], width=2, signed=False))
    addr = Variable("addr", IntDomain([(0, 200)], width=16, signed=False))
    variables = {"mode": mode, "addr": addr}
    
    def evaluator(vars):
        m = vars["mode"]
        values = list(m.domain.values())
        if len(values) == 1:
            return values[0] == 1
        return None
    
    then_props = [RangeConstraintPropagator("addr", 0, 99, width=16)]
    else_props = [RangeConstraintPropagator("addr", 100, 200, width=16)]
    
    cond = ConditionalConstraint(
        evaluator,
        {"mode"},
        then_props,
        else_props
    )
    
    result = cond.propagate(variables)
    
    # No propagation should occur
    assert result.is_fixed_point()
    assert list(addr.domain.values()) == list(range(201))


def test_conditional_constraint_no_else():
    """Test conditional with only then branch"""
    mode = Variable("mode", IntDomain([(1, 1)], width=2, signed=False))
    mode.current_value = 1
    addr = Variable("addr", IntDomain([(0, 200)], width=16, signed=False))
    variables = {"mode": mode, "addr": addr}
    
    def evaluator(vars):
        m = vars["mode"]
        values = list(m.domain.values())
        if len(values) == 1:
            return values[0] == 1
        return None
    
    then_props = [RangeConstraintPropagator("addr", 0, 99, width=16)]
    
    cond = ConditionalConstraint(
        evaluator,
        {"mode"},
        then_props
    )
    
    result = cond.propagate(variables)
    
    assert not result.is_conflict()
    assert max(addr.domain.values()) <= 99


def test_ternary_expression_condition_true():
    """Test ternary when condition is true"""
    # result = (cond ? true_val : false_val), cond = 1
    result = Variable("result", IntDomain([(0, 10)], width=8, signed=False))
    cond = Variable("cond", IntDomain([(1, 1)], width=1, signed=False))
    true_val = Variable("true_val", IntDomain([(5, 5)], width=8, signed=False))
    false_val = Variable("false_val", IntDomain([(3, 3)], width=8, signed=False))
    variables = {"result": result, "cond": cond, "true_val": true_val, "false_val": false_val}
    
    prop = TernaryExpressionPropagator("result", "cond", "true_val", "false_val")
    res = prop.propagate(variables)
    
    # result should equal true_val = 5
    assert not res.is_conflict()
    assert list(result.domain.values()) == [5]


def test_ternary_expression_condition_false():
    """Test ternary when condition is false"""
    # result = (cond ? true_val : false_val), cond = 0
    result = Variable("result", IntDomain([(0, 10)], width=8, signed=False))
    cond = Variable("cond", IntDomain([(0, 0)], width=1, signed=False))
    true_val = Variable("true_val", IntDomain([(5, 5)], width=8, signed=False))
    false_val = Variable("false_val", IntDomain([(3, 3)], width=8, signed=False))
    variables = {"result": result, "cond": cond, "true_val": true_val, "false_val": false_val}
    
    prop = TernaryExpressionPropagator("result", "cond", "true_val", "false_val")
    res = prop.propagate(variables)
    
    # result should equal false_val = 3
    assert not res.is_conflict()
    assert list(result.domain.values()) == [3]


def test_ternary_expression_undetermined():
    """Test ternary when condition is undetermined"""
    # cond can be 0 or 1
    result = Variable("result", IntDomain([(0, 10)], width=8, signed=False))
    cond = Variable("cond", IntDomain([(0, 1)], width=1, signed=False))
    true_val = Variable("true_val", IntDomain([(5, 5)], width=8, signed=False))
    false_val = Variable("false_val", IntDomain([(3, 3)], width=8, signed=False))
    variables = {"result": result, "cond": cond, "true_val": true_val, "false_val": false_val}
    
    prop = TernaryExpressionPropagator("result", "cond", "true_val", "false_val")
    res = prop.propagate(variables)
    
    # No propagation until condition determined
    assert res.is_fixed_point()


def test_ternary_expression_is_satisfied():
    """Test is_satisfied for ternary expression"""
    prop = TernaryExpressionPropagator("result", "cond", "true_val", "false_val")
    
    # cond = 1, result = true_val
    assert prop.is_satisfied({"result": 5, "cond": 1, "true_val": 5, "false_val": 3})
    
    # cond = 0, result = false_val
    assert prop.is_satisfied({"result": 3, "cond": 0, "true_val": 5, "false_val": 3})
    
    # cond = 1, but result != true_val
    assert not prop.is_satisfied({"result": 3, "cond": 1, "true_val": 5, "false_val": 3})
    
    # cond = 0, but result != false_val
    assert not prop.is_satisfied({"result": 5, "cond": 0, "true_val": 5, "false_val": 3})


def test_ternary_expression_conflict():
    """Test ternary conflict when result doesn't match selected value"""
    # result = [0, 2], cond = 1, true_val = 5
    result = Variable("result", IntDomain([(0, 2)], width=8, signed=False))
    cond = Variable("cond", IntDomain([(1, 1)], width=1, signed=False))
    true_val = Variable("true_val", IntDomain([(5, 5)], width=8, signed=False))
    false_val = Variable("false_val", IntDomain([(3, 3)], width=8, signed=False))
    variables = {"result": result, "cond": cond, "true_val": true_val, "false_val": false_val}
    
    prop = TernaryExpressionPropagator("result", "cond", "true_val", "false_val")
    res = prop.propagate(variables)
    
    # Should conflict (result can't be 5)
    assert res.is_conflict()


def test_conditional_affected_variables():
    """Test affected_variables for conditional"""
    then_props = [RangeConstraintPropagator("x", 0, 10, width=8)]
    else_props = [RangeConstraintPropagator("y", 0, 10, width=8)]
    
    def evaluator(vars):
        return None
    
    cond = ConditionalConstraint(evaluator, {"mode"}, then_props, else_props)
    
    affected = cond.affected_variables()
    assert "mode" in affected
    assert "x" in affected
    assert "y" in affected


def test_ternary_affected_variables():
    """Test affected_variables for ternary"""
    prop = TernaryExpressionPropagator("result", "cond", "true_val", "false_val")
    
    affected = prop.affected_variables()
    assert affected == {"result", "cond", "true_val", "false_val"}


def test_conditional_repr():
    """Test string representation"""
    then_props = [RangeConstraintPropagator("x", 0, 10, width=8)]
    else_props = []
    
    def evaluator(vars):
        return None
    
    cond = ConditionalConstraint(evaluator, {"mode"}, then_props, else_props)
    repr_str = repr(cond)
    assert "ConditionalConstraint" in repr_str


def test_ternary_repr():
    """Test ternary string representation"""
    prop = TernaryExpressionPropagator("result", "cond", "true_val", "false_val")
    repr_str = repr(prop)
    assert "TernaryExpression" in repr_str
    assert "result" in repr_str
