"""Tests for function call propagators ($countones, $clog2, user functions)"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.propagators.functions import (
    CountOnesPropagator,
    Clog2Propagator,
    UserFunctionPropagator,
)


# CountOnes tests

def test_countones_forward_propagation():
    """Test countones forward propagation: input -> result"""
    # input can be 0b0000 to 0b1111 (0-15)
    input_var = Variable("input", IntDomain([(0, 15)], width=8, signed=False))
    # result can be 0-8 (enough to hold bit counts)
    result = Variable("result", IntDomain([(0, 8)], width=8, signed=False))
    
    variables = {"input": input_var, "result": result}
    prop = CountOnesPropagator("result", "input")
    
    # Should narrow result to possible bit counts: 0, 1, 2, 3, 4
    # 0b0000 = 0, 0b0001 = 1, ..., 0b1111 = 4
    prop_result = prop.propagate(variables)
    
    assert not prop_result.is_conflict()
    # Result should be in [0, 4]
    assert 0 in list(result.domain.values())
    assert 4 in list(result.domain.values())
    assert 5 not in list(result.domain.values())


def test_countones_backward_propagation():
    """Test countones backward propagation: result -> input"""
    # input can be 0b0000 to 0b1111 (0-15)
    input_var = Variable("input", IntDomain([(0, 15)], width=8, signed=False))
    # result must be exactly 2
    result = Variable("result", IntDomain([(2, 2)], width=8, signed=False))
    
    variables = {"input": input_var, "result": result}
    prop = CountOnesPropagator("result", "input")
    
    prop_result = prop.propagate(variables)
    
    assert not prop_result.is_conflict()
    # Input should be limited to values with exactly 2 bits set
    # 0b0011=3, 0b0101=5, 0b0110=6, 0b1001=9, 0b1010=10, 0b1100=12
    valid_inputs = {3, 5, 6, 9, 10, 12}
    input_values = set(input_var.domain.values())
    assert input_values == valid_inputs


def test_countones_conflict():
    """Test countones conflict detection"""
    # input can only be 0b1111 (15), which has 4 bits set
    input_var = Variable("input", IntDomain([(15, 15)], width=8, signed=False))
    # result must be 2, but input has 4 bits
    result = Variable("result", IntDomain([(2, 2)], width=8, signed=False))
    
    variables = {"input": input_var, "result": result}
    prop = CountOnesPropagator("result", "input")
    
    prop_result = prop.propagate(variables)
    
    assert prop_result.is_conflict()


def test_countones_is_satisfied():
    """Test countones satisfaction checking"""
    prop = CountOnesPropagator("result", "input")
    
    # 0b1011 = 11 has 3 bits set
    assert prop.is_satisfied({"result": 3, "input": 11})
    assert not prop.is_satisfied({"result": 2, "input": 11})
    
    # 0b10000 = 16 has 1 bit set
    assert prop.is_satisfied({"result": 1, "input": 16})


def test_countones_bidirectional():
    """Test countones bidirectional propagation"""
    # Both input and result have some constraints
    input_var = Variable("input", IntDomain([(5, 10)], width=8, signed=False))
    result = Variable("result", IntDomain([(2, 3)], width=8, signed=False))
    
    variables = {"input": input_var, "result": result}
    prop = CountOnesPropagator("result", "input")
    
    prop_result = prop.propagate(variables)
    
    assert not prop_result.is_conflict()
    # 5=0b0101(2), 6=0b0110(2), 7=0b0111(3), 9=0b1001(2), 10=0b1010(2)
    # Only 5, 6, 7, 9, 10 have 2 or 3 bits (8=0b1000 has 1 bit)
    input_values = set(input_var.domain.values())
    assert 5 in input_values
    assert 6 in input_values
    assert 7 in input_values
    assert 8 not in input_values
    assert 9 in input_values
    assert 10 in input_values


# Clog2 tests

def test_clog2_basic_values():
    """Test clog2 for known values"""
    prop = Clog2Propagator("result", "input")
    
    # Test known clog2 values
    assert prop._clog2(0) == 0
    assert prop._clog2(1) == 0
    assert prop._clog2(2) == 1
    assert prop._clog2(3) == 2
    assert prop._clog2(4) == 2
    assert prop._clog2(5) == 3
    assert prop._clog2(8) == 3
    assert prop._clog2(9) == 4
    assert prop._clog2(16) == 4
    assert prop._clog2(17) == 5


def test_clog2_forward_propagation():
    """Test clog2 forward propagation: input -> result"""
    # input can be 0-15
    input_var = Variable("input", IntDomain([(0, 15)], width=8, signed=False))
    # result can be 0-8
    result = Variable("result", IntDomain([(0, 8)], width=8, signed=False))
    
    variables = {"input": input_var, "result": result}
    prop = Clog2Propagator("result", "input")
    
    prop_result = prop.propagate(variables)
    
    assert not prop_result.is_conflict()
    # For 0-15, clog2 ranges from 0 to 4
    # 0->0, 1->0, 2->1, 3-4->2, 5-8->3, 9-15->4
    result_values = set(result.domain.values())
    assert 0 in result_values
    assert 4 in result_values
    assert 5 not in result_values


def test_clog2_backward_propagation():
    """Test clog2 backward propagation: result -> input"""
    # input can be 0-15
    input_var = Variable("input", IntDomain([(0, 15)], width=8, signed=False))
    # result must be exactly 2
    result = Variable("result", IntDomain([(2, 2)], width=8, signed=False))
    
    variables = {"input": input_var, "result": result}
    prop = Clog2Propagator("result", "input")
    
    prop_result = prop.propagate(variables)
    
    assert not prop_result.is_conflict()
    # clog2(x) == 2 for x in [3, 4]
    input_values = set(input_var.domain.values())
    assert input_values == {3, 4}


def test_clog2_conflict():
    """Test clog2 conflict detection"""
    # input can only be 16
    input_var = Variable("input", IntDomain([(16, 16)], width=8, signed=False))
    # result must be 2, but clog2(16) = 4
    result = Variable("result", IntDomain([(2, 2)], width=8, signed=False))
    
    variables = {"input": input_var, "result": result}
    prop = Clog2Propagator("result", "input")
    
    prop_result = prop.propagate(variables)
    
    assert prop_result.is_conflict()


def test_clog2_is_satisfied():
    """Test clog2 satisfaction checking"""
    prop = Clog2Propagator("result", "input")
    
    assert prop.is_satisfied({"result": 0, "input": 0})
    assert prop.is_satisfied({"result": 0, "input": 1})
    assert prop.is_satisfied({"result": 1, "input": 2})
    assert prop.is_satisfied({"result": 2, "input": 3})
    assert prop.is_satisfied({"result": 2, "input": 4})
    assert prop.is_satisfied({"result": 3, "input": 5})
    
    assert not prop.is_satisfied({"result": 1, "input": 3})
    assert not prop.is_satisfied({"result": 2, "input": 2})


def test_clog2_range_constraint():
    """Test clog2 with range constraint"""
    # input in [8, 16]
    input_var = Variable("input", IntDomain([(8, 16)], width=8, signed=False))
    # result unconstrained
    result = Variable("result", IntDomain([(0, 10)], width=8, signed=False))
    
    variables = {"input": input_var, "result": result}
    prop = Clog2Propagator("result", "input")
    
    prop_result = prop.propagate(variables)
    
    assert not prop_result.is_conflict()
    # clog2(8) = 3, clog2(9-16) = 4
    result_values = set(result.domain.values())
    assert result_values == {3, 4}


# User function tests

def test_user_function_basic():
    """Test user function propagation"""
    # Simple function: result = x + y
    def add_func(x, y):
        return x + y
    
    x = Variable("x", IntDomain([(5, 5)], width=8, signed=False))
    y = Variable("y", IntDomain([(3, 3)], width=8, signed=False))
    result = Variable("result", IntDomain([(0, 20)], width=8, signed=False))
    
    variables = {"x": x, "y": y, "result": result}
    prop = UserFunctionPropagator("result", ["x", "y"], add_func, "add")
    
    # Assign variables
    x.assign(5)
    y.assign(3)
    
    prop_result = prop.propagate(variables)
    
    assert not prop_result.is_conflict()
    # Result should be constrained to 8
    assert result.domain.is_singleton()
    assert 8 in list(result.domain.values())


def test_user_function_conflict():
    """Test user function conflict"""
    def square_func(x):
        return x * x
    
    x = Variable("x", IntDomain([(5, 5)], width=8, signed=False))
    result = Variable("result", IntDomain([(10, 20)], width=8, signed=False))
    
    variables = {"x": x, "result": result}
    prop = UserFunctionPropagator("result", ["x"], square_func, "square")
    
    # Assign x
    x.assign(5)
    
    prop_result = prop.propagate(variables)
    
    # 5*5 = 25, which is outside [10, 20]
    assert prop_result.is_conflict()


def test_user_function_unassigned():
    """Test user function with unassigned variables"""
    def add_func(x, y):
        return x + y
    
    x = Variable("x", IntDomain([(0, 10)], width=8, signed=False))
    y = Variable("y", IntDomain([(0, 10)], width=8, signed=False))
    result = Variable("result", IntDomain([(0, 30)], width=8, signed=False))
    
    variables = {"x": x, "y": y, "result": result}
    prop = UserFunctionPropagator("result", ["x", "y"], add_func, "add")
    
    # Don't assign variables - should reach fixed point without changes
    prop_result = prop.propagate(variables)
    
    assert not prop_result.is_conflict()
    assert prop_result.status == prop_result.status.FIXED_POINT


def test_user_function_is_satisfied():
    """Test user function satisfaction checking"""
    def multiply_func(x, y):
        return x * y
    
    prop = UserFunctionPropagator("result", ["x", "y"], multiply_func, "multiply")
    
    assert prop.is_satisfied({"result": 20, "x": 4, "y": 5})
    assert not prop.is_satisfied({"result": 15, "x": 4, "y": 5})


def test_user_function_exception():
    """Test user function that raises exception"""
    def div_func(x, y):
        return x // y
    
    x = Variable("x", IntDomain([(10, 10)], width=8, signed=False))
    y = Variable("y", IntDomain([(0, 0)], width=8, signed=False))
    result = Variable("result", IntDomain([(0, 10)], width=8, signed=False))
    
    variables = {"x": x, "y": y, "result": result}
    prop = UserFunctionPropagator("result", ["x", "y"], div_func, "div")
    
    # Assign variables
    x.assign(10)
    y.assign(0)
    
    prop_result = prop.propagate(variables)
    
    # Division by zero should cause conflict
    assert prop_result.is_conflict()


# Integration tests

def test_countones_with_comparison():
    """Test countones in a constraint with comparison"""
    # Constraint: $countones(x) > 2
    x = Variable("x", IntDomain([(0, 15)], width=8, signed=False))
    count = Variable("count", IntDomain([(0, 8)], width=8, signed=False))
    threshold = Variable("threshold", IntDomain([(2, 2)], width=8, signed=False))
    
    variables = {"x": x, "count": count, "threshold": threshold}
    
    # First propagate countones
    countones_prop = CountOnesPropagator("count", "x")
    result1 = countones_prop.propagate(variables)
    assert not result1.is_conflict()
    
    # Then constrain count > 2
    from zuspec.dataclasses.solver.propagators import GreaterThanPropagator
    gt_prop = GreaterThanPropagator("count", "threshold")
    result2 = gt_prop.propagate(variables)
    assert not result2.is_conflict()
    
    # count should be in [3, 4]
    count_values = set(count.domain.values())
    assert count_values == {3, 4}
    
    # Propagate countones again to filter x
    result3 = countones_prop.propagate(variables)
    assert not result3.is_conflict()
    
    # x should only have values with 3 or 4 bits set
    # 3 bits: 7, 11, 13, 14
    # 4 bits: 15
    x_values = set(x.domain.values())
    assert x_values == {7, 11, 13, 14, 15}


def test_clog2_sizing_constraint():
    """Test clog2 for address width sizing"""
    # mem_size in [16, 64], addr_bits = $clog2(mem_size)
    mem_size = Variable("mem_size", IntDomain([(16, 64)], width=8, signed=False))
    addr_bits = Variable("addr_bits", IntDomain([(0, 10)], width=8, signed=False))
    
    variables = {"mem_size": mem_size, "addr_bits": addr_bits}
    prop = Clog2Propagator("addr_bits", "mem_size")
    
    result = prop.propagate(variables)
    assert not result.is_conflict()
    
    # clog2(16) = 4, clog2(17-32) = 5, clog2(33-64) = 6
    addr_values = set(addr_bits.domain.values())
    assert addr_values == {4, 5, 6}


# Repr tests

def test_countones_repr():
    """Test string representation"""
    prop = CountOnesPropagator("result", "input")
    repr_str = repr(prop)
    assert "CountOnesPropagator" in repr_str
    assert "result" in repr_str
    assert "input" in repr_str


def test_clog2_repr():
    """Test string representation"""
    prop = Clog2Propagator("result", "input")
    repr_str = repr(prop)
    assert "Clog2Propagator" in repr_str
    assert "result" in repr_str
    assert "input" in repr_str


def test_user_function_repr():
    """Test string representation"""
    def func(x):
        return x * 2
    
    prop = UserFunctionPropagator("result", ["input"], func, "double")
    repr_str = repr(prop)
    assert "UserFunctionPropagator" in repr_str
    assert "result" in repr_str
    assert "double" in repr_str
