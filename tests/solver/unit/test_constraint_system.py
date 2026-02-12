"""Tests for ConstraintSystem class"""

import pytest
from zuspec.dataclasses.solver.core.constraint_system import ConstraintSystem
from zuspec.dataclasses.solver.core.variable import Variable, VarKind
from zuspec.dataclasses.solver.core.constraint import Constraint
from zuspec.dataclasses.solver.core.domain import IntDomain


class SimpleConstraint(Constraint):
    """Simple constraint for testing"""
    
    def is_satisfied(self, assignment):
        return True


class TestConstraintSystem:
    """Test ConstraintSystem functionality"""
    
    def test_creation(self):
        """Test creating empty constraint system"""
        cs = ConstraintSystem()
        assert len(cs.variables) == 0
        assert len(cs.constraints) == 0
        assert len(cs.connected_components) == 0
    
    def test_add_variable(self):
        """Test adding variable to system"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain)
        
        cs.add_variable(var)
        assert len(cs.variables) == 1
        assert cs.get_variable("x") == var
    
    def test_add_duplicate_variable(self):
        """Test adding duplicate variable raises error"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var1 = Variable("x", domain)
        var2 = Variable("x", domain)
        
        cs.add_variable(var1)
        with pytest.raises(ValueError):
            cs.add_variable(var2)
    
    def test_add_randc_variable(self):
        """Test adding randc variable"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain, VarKind.RANDC)
        
        cs.add_variable(var)
        assert len(cs.randc_variables) == 1
        assert cs.randc_variables[0] == var
    
    def test_add_constraint(self):
        """Test adding constraint to system"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var = Variable("x", domain)
        cs.add_variable(var)
        
        constraint = SimpleConstraint({var})
        cs.add_constraint(constraint)
        
        assert len(cs.constraints) == 1
        assert cs.constraints[0] == constraint
    
    def test_add_ordering_constraint(self):
        """Test adding ordering constraint"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var1 = Variable("x", domain)
        var2 = Variable("y", domain)
        
        cs.add_variable(var1)
        cs.add_variable(var2)
        
        # Add constraint: solve x before y
        cs.add_ordering_constraint(var1, var2)
        
        assert var1 in var2.order_constraints
    
    def test_add_circular_ordering_constraint(self):
        """Test that circular ordering constraints are detected"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var1 = Variable("x", domain)
        var2 = Variable("y", domain)
        var3 = Variable("z", domain)
        
        cs.add_variable(var1)
        cs.add_variable(var2)
        cs.add_variable(var3)
        
        # Create chain: x before y, y before z
        cs.add_ordering_constraint(var1, var2)
        cs.add_ordering_constraint(var2, var3)
        
        # Try to close the loop: z before x (should fail)
        with pytest.raises(ValueError):
            cs.add_ordering_constraint(var3, var1)
    
    def test_compute_solve_order(self):
        """Test computing solve order"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var1 = Variable("x", domain)
        var2 = Variable("y", domain)
        var3 = Variable("z", domain)
        
        cs.add_variable(var1)
        cs.add_variable(var2)
        cs.add_variable(var3)
        
        # Create ordering: x before y, y before z
        cs.add_ordering_constraint(var1, var2)
        cs.add_ordering_constraint(var2, var3)
        
        cs.compute_solve_order()
        
        # x should come before y, y before z
        x_idx = cs.solve_order.index(var1)
        y_idx = cs.solve_order.index(var2)
        z_idx = cs.solve_order.index(var3)
        
        assert x_idx < y_idx < z_idx
    
    def test_compute_connected_components_single(self):
        """Test computing connected components with single component"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var1 = Variable("x", domain)
        var2 = Variable("y", domain)
        
        cs.add_variable(var1)
        cs.add_variable(var2)
        
        # Add constraint linking both variables
        constraint = SimpleConstraint({var1, var2})
        cs.add_constraint(constraint)
        
        cs.compute_connected_components()
        
        assert len(cs.connected_components) == 1
        assert cs.connected_components[0] == {var1, var2}
    
    def test_compute_connected_components_multiple(self):
        """Test computing connected components with multiple components"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var1 = Variable("x", domain)
        var2 = Variable("y", domain)
        var3 = Variable("z", domain)
        var4 = Variable("w", domain)
        
        cs.add_variable(var1)
        cs.add_variable(var2)
        cs.add_variable(var3)
        cs.add_variable(var4)
        
        # Add constraints: x-y in one component, z-w in another
        constraint1 = SimpleConstraint({var1, var2})
        constraint2 = SimpleConstraint({var3, var4})
        cs.add_constraint(constraint1)
        cs.add_constraint(constraint2)
        
        cs.compute_connected_components()
        
        assert len(cs.connected_components) == 2
        component_sets = [set(c) for c in cs.connected_components]
        assert {var1, var2} in component_sets
        assert {var3, var4} in component_sets
    
    def test_get_constraints_for_variable(self):
        """Test getting constraints for a variable"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 10)], width=32, signed=False)
        var1 = Variable("x", domain)
        var2 = Variable("y", domain)
        
        cs.add_variable(var1)
        cs.add_variable(var2)
        
        constraint1 = SimpleConstraint({var1})
        constraint2 = SimpleConstraint({var1, var2})
        constraint3 = SimpleConstraint({var2})
        
        cs.add_constraint(constraint1)
        cs.add_constraint(constraint2)
        cs.add_constraint(constraint3)
        
        # var1 should appear in constraint1 and constraint2
        var1_constraints = cs.get_constraints_for_variable(var1)
        assert len(var1_constraints) == 2
        assert constraint1 in var1_constraints
        assert constraint2 in var1_constraints
    
    def test_reset_randc_variables(self):
        """Test resetting randc variables"""
        cs = ConstraintSystem()
        domain = IntDomain([(0, 4)], width=32, signed=False)
        var = Variable("x", domain, VarKind.RANDC)
        
        cs.add_variable(var)
        
        # Mark some values as used
        var.assign(0)
        var.unassign()
        var.assign(1)
        var.unassign()
        
        assert len(var.randc_state.used_values) == 2
        
        # Reset
        cs.reset_randc_variables()
        assert len(var.randc_state.used_values) == 0
