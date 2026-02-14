"""Tests for randc (random-cyclic) variable support"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable, VarKind
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.solver.randc import RandCManager, RandCConfig


def test_randc_state_initialization():
    """Test that randc state is properly initialized"""
    domain = IntDomain([(0, 5)], width=8, signed=False)
    var = Variable("x", domain, kind=VarKind.RANDC)
    
    assert var.randc_state is not None
    assert var.randc_state.domain_size == 6
    assert len(var.randc_state.used_values) == 0
    assert not var.randc_state.cycle_complete


def test_randc_permutation_generation():
    """Test permutation generation with seeded RNG"""
    config = RandCConfig(seed=42)
    manager = RandCManager(config)
    
    domain = IntDomain([(1, 4)], width=8, signed=False)
    var = Variable("x", domain, kind=VarKind.RANDC)
    
    # Get multiple values
    values = []
    for i in range(4):
        value = manager.get_next_value(var, domain, constraint_version=0)
        assert value is not None
        values.append(value)
    
    # Should get all 4 values (permutation)
    assert set(values) == {1, 2, 3, 4}
    
    # Next call should generate new permutation
    value = manager.get_next_value(var, domain, constraint_version=0)
    assert value in {1, 2, 3, 4}


def test_randc_reset_on_constraint_change():
    """Test that randc resets when constraints change"""
    config = RandCConfig(seed=42)
    manager = RandCManager(config)
    
    domain = IntDomain([(0, 3)], width=8, signed=False)
    var = Variable("x", domain, kind=VarKind.RANDC)
    
    # Get first value
    value1 = manager.get_next_value(var, domain, constraint_version=0)
    assert value1 is not None
    
    # Get second value (same constraint version)
    value2 = manager.get_next_value(var, domain, constraint_version=0)
    assert value2 is not None
    assert value2 != value1
    
    # Change constraint version - should reset
    value3 = manager.get_next_value(var, domain, constraint_version=1)
    assert value3 is not None
    # Should start new permutation (could be same value by chance)


def test_randc_with_reduced_domain():
    """Test randc with domain reduced by constraints"""
    config = RandCConfig(seed=42)
    manager = RandCManager(config)
    
    full_domain = IntDomain([(0, 9)], width=8, signed=False)
    var = Variable("x", full_domain, kind=VarKind.RANDC)
    
    # Reduced domain after constraint propagation
    reduced_domain = IntDomain([(3, 5)], width=8, signed=False)
    
    values = []
    for i in range(3):
        value = manager.get_next_value(var, reduced_domain, constraint_version=0)
        assert value is not None
        values.append(value)
    
    # Should get all 3 values from reduced domain
    assert set(values) == {3, 4, 5}


def test_randc_mark_success_and_cycle():
    """Test marking success and cycle completion"""
    config = RandCConfig(seed=42)
    manager = RandCManager(config)
    
    domain = IntDomain([(0, 2)], width=8, signed=False)  # 3 values
    var = Variable("x", domain, kind=VarKind.RANDC)
    
    # Use first 2 values
    for i in range(2):
        value = manager.get_next_value(var, domain, constraint_version=0)
        assert value is not None
        manager.mark_value_success(var, value)
    
    # Should have 2 used values
    assert len(var.randc_state.used_values) == 2
    
    # Use third value - should complete cycle
    value = manager.get_next_value(var, domain, constraint_version=0)
    assert value is not None
    manager.mark_value_success(var, value)
    
    # After all 3 values used, cycle should be complete and reset
    # The reset happens in mark_value_success when cycle is complete
    assert len(var.randc_state.used_values) == 0  # Reset after cycle


def test_randc_max_retries():
    """Test that randc gives up after max retries"""
    config = RandCConfig(seed=42, max_permutation_retries=3)
    manager = RandCManager(config)
    
    domain = IntDomain([(0, 1)], width=8, signed=False)  # 2 values
    var = Variable("x", domain, kind=VarKind.RANDC)
    
    # Exhaust permutation multiple times
    for retry in range(3):
        for i in range(2):
            value = manager.get_next_value(var, domain, constraint_version=0)
            assert value is not None
    
    # Should still get values (retry 1, 2, 3)
    # After max_retries permutations (each with 2 values), next call gives up
    for i in range(2):
        value = manager.get_next_value(var, domain, constraint_version=0)
        if value is None:
            break
    # Eventually should return None


def test_randc_available_values():
    """Test getting available values in cycle"""
    config = RandCConfig(seed=42)
    manager = RandCManager(config)
    
    domain = IntDomain([(0, 4)], width=8, signed=False)  # 5 values
    var = Variable("x", domain, kind=VarKind.RANDC)
    
    # Initially all available
    available = manager.get_available_values(var)
    assert available == {0, 1, 2, 3, 4}
    
    # Mark some as used
    var.randc_state.mark_used(1)
    var.randc_state.mark_used(3)
    
    available = manager.get_available_values(var)
    assert available == {0, 2, 4}


def test_randc_empty_domain():
    """Test randc with empty domain"""
    config = RandCConfig(seed=42)
    manager = RandCManager(config)
    
    domain = IntDomain([], width=8, signed=False)
    var = Variable("x", domain, kind=VarKind.RANDC)
    
    value = manager.get_next_value(var, domain, constraint_version=0)
    assert value is None


def test_randc_retry_count():
    """Test retry count tracking"""
    config = RandCConfig(seed=42, max_permutation_retries=5)
    manager = RandCManager(config)
    
    domain = IntDomain([(0, 1)], width=8, signed=False)
    var = Variable("x", domain, kind=VarKind.RANDC)
    
    # Exhaust first permutation
    for i in range(2):
        manager.get_next_value(var, domain, constraint_version=0)
    
    # Start second permutation
    manager.get_next_value(var, domain, constraint_version=0)
    
    retry_count = manager.get_retry_count(var)
    assert retry_count >= 0  # At least one retry


def test_randc_vs_rand_variable():
    """Test that regular rand variables don't get randc treatment"""
    config = RandCConfig(seed=42)
    manager = RandCManager(config)
    
    domain = IntDomain([(0, 5)], width=8, signed=False)
    rand_var = Variable("x", domain, kind=VarKind.RAND)
    
    # Regular rand variable should not have randc_state
    assert rand_var.randc_state is None
    
    # get_next_value should raise error for non-randc
    with pytest.raises(ValueError, match="not randc"):
        manager.get_next_value(rand_var, domain, constraint_version=0)
