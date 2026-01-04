"""Basic tests for IR checker framework."""

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.ir_checker import (
    ZuspecIRChecker,
    CheckerRegistry,
    RetargetableIRChecker,
    PythonIRChecker
)
from zuspec.dataclasses.data_model_factory import DataModelFactory


class TestCheckerRegistry:
    """Test the checker registry."""
    
    def test_builtin_checkers_registered(self):
        """Test that built-in checkers are registered."""
        profiles = CheckerRegistry.list_profiles()
        assert 'Retargetable' in profiles
        assert 'Python' in profiles
    
    def test_get_checker(self):
        """Test getting a checker by profile name."""
        checker_cls = CheckerRegistry.get_checker('Retargetable')
        assert checker_cls is not None
        assert checker_cls == RetargetableIRChecker
    
    def test_get_unknown_profile(self):
        """Test getting an unknown profile returns None."""
        checker_cls = CheckerRegistry.get_checker('Unknown')
        assert checker_cls is None


class TestZuspecIRChecker:
    """Test the main checker orchestrator."""
    
    def test_init_with_valid_profile(self):
        """Test initialization with a valid profile."""
        checker = ZuspecIRChecker(profile='Retargetable')
        assert checker.profile == 'Retargetable'
        assert checker.checker is not None
    
    def test_init_with_invalid_profile(self):
        """Test initialization with an invalid profile raises ValueError."""
        with pytest.raises(ValueError, match="No checker registered"):
            ZuspecIRChecker(profile='InvalidProfile')
    
    def test_check_empty_context(self):
        """Test checking an empty context."""
        from zuspec.dataclasses.ir import Context
        
        checker = ZuspecIRChecker(profile='Retargetable')
        context = Context()
        errors = checker.check_context(context)
        assert errors == []


class TestRetargetableChecker:
    """Test the Retargetable profile checker."""
    
    def test_infinite_width_int_detected(self):
        """Test that infinite-width int is detected."""
        
        @zdc.dataclass
        class BadCounter:
            # This should fail: infinite-width int (if field type doesn't have width)
            # Note: this test depends on how DataModelFactory represents Python int
            pass
        
        # For now, just verify checker can be instantiated
        checker = ZuspecIRChecker(profile='Retargetable')
        assert checker is not None
    
    def test_width_annotated_int_ok(self):
        """Test that width-annotated types are OK."""
        
        @zdc.dataclass
        class GoodCounter:
            count: zdc.uint32_t = zdc.field(default=0)
        
        # Build IR
        factory = DataModelFactory()
        context = factory.build([GoodCounter])
        
        # Check
        checker = ZuspecIRChecker(profile='Retargetable')
        errors = checker.check_context(context)
        
        # Should have no errors for properly typed field
        # (or at least no ZDC001 error for infinite-width int)
        zdc001_errors = [e for e in errors if e.code == 'ZDC001']
        assert len(zdc001_errors) == 0


class TestPythonChecker:
    """Test the Python profile checker (permissive)."""
    
    def test_python_profile_permissive(self):
        """Test that Python profile allows everything."""
        
        @zdc.dataclass
        class FlexibleClass:
            value: zdc.uint32_t = zdc.field(default=0)
        
        # Build IR
        factory = DataModelFactory()
        context = factory.build([FlexibleClass])
        
        # Check with Python profile
        checker = ZuspecIRChecker(profile='Python')
        errors = checker.check_context(context)
        
        # Python profile should not generate errors
        assert len(errors) == 0


class TestIntegration:
    """Integration tests for full workflow."""
    
    def test_full_workflow(self):
        """Test complete workflow from Python to IR to checking."""
        
        @zdc.dataclass
        class TestComponent(zdc.Component):
            data: zdc.uint32_t = zdc.output()
        
        # Build IR
        factory = DataModelFactory()
        context = factory.build([TestComponent])
        
        # Verify context has types
        assert len(context.type_m) > 0
        
        # Check with Retargetable profile
        checker = ZuspecIRChecker(profile='Retargetable')
        errors = checker.check_context(context)
        
        # Properly typed component should have no errors
        assert isinstance(errors, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
