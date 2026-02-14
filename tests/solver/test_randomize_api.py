"""Tests for the high-level randomize() API"""

import pytest
from zuspec.dataclasses import (
    dataclass, field, constraint, randomize, RandomizationError
)
from zuspec.dataclasses.solver.core.variable import Variable, VarKind
from zuspec.dataclasses.solver.core.domain import IntDomain
from zuspec.dataclasses.ir.data_type import DataTypeStruct, DataTypeInt
from zuspec.dataclasses.ir.fields import Field


class TestRandomizeAPI:
    """Test suite for randomize() API"""
    
    @pytest.mark.skip(reason="Test uses incomplete IR struct construction")
    def test_randomize_simple_unconstrained(self):
        """Test randomizing a simple object with no constraints"""
        # Create a simple IR struct for testing
        struct_type = self._create_test_struct_simple()
        
        # Mock object
        class TestObj:
            _zdc_struct = struct_type
            value = 0
        
        obj = TestObj()
        
        # This should work once we have proper IR struct setup
        # For now, we expect it to fail with BuildError
        with pytest.raises(RandomizationError):
            randomize(obj)
    
    def test_randomize_with_seed_reproducibility(self):
        """Test that same seed produces same results"""
        # This test will be implemented once we have full IR integration
        pass
    
    def test_randomize_unsat_returns_false(self):
        """Test that UNSAT constraints return False"""
        # Create a struct with contradictory constraints
        # value < 10 AND value > 20 => UNSAT
        pass
    
    def test_randomize_updates_fields(self):
        """Test that successful randomization updates object fields"""
        pass
    
    def test_randomize_with_constraints(self):
        """Test randomization with @constraint methods"""
        pass
    
    def test_randomize_randc_cycling(self):
        """Test randc variables cycle through values"""
        pass
    
    def test_randomize_invalid_object_raises(self):
        """Test that invalid objects raise RandomizationError"""
        # Object without _zdc_struct or random fields
        class BadObj:
            value = 0
        
        obj = BadObj()
        # Should now raise "No random variables found" instead
        with pytest.raises(RandomizationError, match="No random variables found|Cannot extract IR struct type"):
            randomize(obj)
    
    def test_randomize_with_invalid_object(self):
        """Test that randomize_with() on invalid object raises RandomizationError"""
        from zuspec.dataclasses.solver.api import randomize_with
        
        class TestObj:
            value = 0
        
        obj = TestObj()
        # Should raise RandomizationError for object without random variables
        with pytest.raises(RandomizationError, match="No random variables found"):
            with randomize_with(obj):
                assert obj.value > 0
    
    # Helper methods
    
    def _create_test_struct_simple(self) -> DataTypeStruct:
        """Create a simple test struct with one random field"""
        # Create a field
        field_type = DataTypeInt(bits=8, signed=False)
        field_obj = Field(name="value", datatype=field_type)
        
        # Create struct
        struct = DataTypeStruct(name="TestStruct")
        # Note: Need to check actual DataTypeStruct API for adding fields
        # This is a placeholder
        
        return struct


class TestRandomizationResult:
    """Test the RandomizationResult helper class"""
    
    def test_result_success(self):
        """Test successful result"""
        from zuspec.dataclasses.solver.api import RandomizationResult
        
        result = RandomizationResult(success=True, assignment={"x": 42})
        assert result.success
        assert bool(result) is True
        assert result.assignment == {"x": 42}
        assert result.error is None
        assert "success=True" in repr(result)
    
    def test_result_failure(self):
        """Test failed result"""
        from zuspec.dataclasses.solver.api import RandomizationResult
        
        result = RandomizationResult(success=False, error="UNSAT")
        assert not result.success
        assert bool(result) is False
        assert result.assignment == {}
        assert result.error == "UNSAT"
        assert "success=False" in repr(result)


class TestApplySolution:
    """Test the _apply_solution helper"""
    
    def test_apply_simple_field(self):
        """Test applying solution to simple field"""
        from zuspec.dataclasses.solver.api import _apply_solution
        from zuspec.dataclasses.solver.core.constraint_system import ConstraintSystem
        
        class TestObj:
            value = 0
        
        obj = TestObj()
        system = ConstraintSystem()
        assignment = {"value": 42}
        
        _apply_solution(obj, assignment, system)
        assert obj.value == 42
    
    def test_apply_nested_field(self):
        """Test applying solution to nested field"""
        from zuspec.dataclasses.solver.api import _apply_solution
        from zuspec.dataclasses.solver.core.constraint_system import ConstraintSystem
        
        class Inner:
            data = 0
        
        class Outer:
            inner = Inner()
        
        obj = Outer()
        system = ConstraintSystem()
        assignment = {"inner.data": 123}
        
        _apply_solution(obj, assignment, system)
        assert obj.inner.data == 123
    
    def test_apply_nonexistent_field_skipped(self):
        """Test that nonexistent fields are skipped (internal variables)"""
        from zuspec.dataclasses.solver.api import _apply_solution
        from zuspec.dataclasses.solver.core.constraint_system import ConstraintSystem
        
        class TestObj:
            value = 0
        
        obj = TestObj()
        system = ConstraintSystem()
        assignment = {"value": 42, "internal_var": 99}
        
        # Should not raise
        _apply_solution(obj, assignment, system)
        assert obj.value == 42
        assert not hasattr(obj, "internal_var")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
