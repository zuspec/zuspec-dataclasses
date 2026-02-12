"""Tests for Variable class"""

import pytest
from zuspec.dataclasses.solver.core.variable import Variable, VarKind, RandCState
from zuspec.dataclasses.solver.core.domain import IntDomain


class TestVariable:
    """Test Variable functionality"""
    
    def test_creation_rand(self):
        """Test creating a regular rand variable"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain, VarKind.RAND)
        
        assert var.name == "x"
        assert var.kind == VarKind.RAND
        assert not var.is_assigned()
        assert var.randc_state is None
    
    def test_creation_randc(self):
        """Test creating a randc variable"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain, VarKind.RANDC)
        
        assert var.kind == VarKind.RANDC
        assert var.randc_state is not None
        assert var.randc_state.domain_size == 11
    
    def test_assign_value(self):
        """Test assigning a value to variable"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain)
        
        var.assign(5)
        assert var.is_assigned()
        assert var.current_value == 5
    
    def test_assign_invalid_value(self):
        """Test assigning value outside domain raises error"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain)
        
        with pytest.raises(ValueError):
            var.assign(20)
    
    def test_unassign(self):
        """Test unassigning a variable"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain)
        
        var.assign(5)
        var.unassign()
        assert not var.is_assigned()
        assert var.current_value is None
    
    def test_get_effective_domain_rand(self):
        """Test effective domain for rand variable"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain, VarKind.RAND)
        
        effective = var.get_effective_domain()
        assert effective == domain
    
    def test_get_effective_domain_randc(self):
        """Test effective domain for randc variable"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain, VarKind.RANDC)
        
        # Initially, effective domain equals base domain
        effective = var.get_effective_domain()
        assert effective.size() == 11
        
        # Assign a value
        var.assign(5)
        
        # Effective domain should now exclude 5
        effective = var.get_effective_domain()
        assert effective.size() == 10
        assert 5 not in list(effective.values())


class TestRandCState:
    """Test RandCState functionality"""
    
    def test_creation(self):
        """Test creating randc state"""
        state = RandCState(domain_size=10)
        assert state.domain_size == 10
        assert len(state.used_values) == 0
        assert not state.cycle_complete
    
    def test_mark_used(self):
        """Test marking values as used"""
        state = RandCState(domain_size=5)
        
        state.mark_used(1)
        assert 1 in state.used_values
        assert not state.cycle_complete
        
        state.mark_used(2)
        assert len(state.used_values) == 2
    
    def test_cycle_completion(self):
        """Test cycle completion detection"""
        state = RandCState(domain_size=3)
        
        state.mark_used(0)
        assert not state.cycle_complete
        
        state.mark_used(1)
        assert not state.cycle_complete
        
        state.mark_used(2)
        assert state.cycle_complete
    
    def test_reset_cycle(self):
        """Test resetting cycle"""
        state = RandCState(domain_size=3)
        
        state.mark_used(0)
        state.mark_used(1)
        state.mark_used(2)
        assert state.cycle_complete
        
        state.reset_cycle()
        assert len(state.used_values) == 0
        assert not state.cycle_complete
    
    def test_get_available_domain(self):
        """Test getting available domain with used values removed"""
        domain = IntDomain([(0, 4)], width=32, signed=False)
        state = RandCState(domain_size=5)
        
        # Mark some values as used
        state.mark_used(1)
        state.mark_used(3)
        
        # Get available domain
        available = state.get_available_domain(domain)
        assert available.size() == 3
        assert set(available.values()) == {0, 2, 4}
