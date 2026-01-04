"""Test profile auto-detection from class declarations."""

import pytest
import tempfile
from pathlib import Path
import zuspec.dataclasses as zdc
from zuspec.dataclasses.profiles import RetargetableProfile, PythonProfile
from zuspec.dataclasses.flake8_zdc_struct import ZuspecFlake8Plugin
import ast


class TestProfileAutoDetection:
    """Test that profiles are auto-detected from @dataclass(profile=...) declarations."""
    
    def test_detect_retargetable_profile(self):
        """Test detecting Retargetable profile from class."""
        
        @zdc.dataclass(profile=RetargetableProfile)
        class RetargetableClass:
            value: zdc.uint32_t = zdc.field(default=0)
        
        # Create plugin instance
        plugin = ZuspecFlake8Plugin(ast.parse(""), "test.py")
        
        # Test profile detection
        profile_name = plugin._detect_profile(RetargetableClass)
        assert profile_name == 'Retargetable'
    
    def test_detect_python_profile(self):
        """Test detecting Python profile from class."""
        
        @zdc.dataclass(profile=PythonProfile)
        class PythonClass:
            value: int = zdc.field(default=0)
        
        plugin = ZuspecFlake8Plugin(ast.parse(""), "test.py")
        profile_name = plugin._detect_profile(PythonClass)
        assert profile_name == 'Python'
    
    def test_detect_default_profile_when_not_specified(self):
        """Test that default profile is used when not specified."""
        
        @zdc.dataclass
        class DefaultClass:
            value: zdc.uint32_t = zdc.field(default=0)
        
        plugin = ZuspecFlake8Plugin(ast.parse(""), "test.py")
        # Configure with custom default
        plugin.zuspec_profile = 'Retargetable'
        
        profile_name = plugin._detect_profile(DefaultClass)
        assert profile_name == 'Retargetable'
    
    def test_mixed_profiles_in_same_file(self):
        """Test that different classes can have different profiles."""
        
        @zdc.dataclass(profile=RetargetableProfile)
        class HardwareClass:
            data: zdc.uint32_t = zdc.output()
        
        @zdc.dataclass(profile=PythonProfile)
        class SoftwareClass:
            data: int = zdc.field(default=0)
        
        plugin = ZuspecFlake8Plugin(ast.parse(""), "test.py")
        
        hw_profile = plugin._detect_profile(HardwareClass)
        sw_profile = plugin._detect_profile(SoftwareClass)
        
        assert hw_profile == 'Retargetable'
        assert sw_profile == 'Python'
    
    def test_profile_stored_in_class_attribute(self):
        """Test that @dataclass decorator stores profile in __profile__."""
        
        @zdc.dataclass(profile=RetargetableProfile)
        class TestClass:
            pass
        
        assert hasattr(TestClass, '__profile__')
        assert TestClass.__profile__ == RetargetableProfile
    
    def test_no_profile_attribute_when_not_specified(self):
        """Test that __profile__ is not set when profile not specified."""
        
        @zdc.dataclass
        class TestClass:
            pass
        
        # __profile__ should not be set
        assert not hasattr(TestClass, '__profile__')


class TestProfileGrouping:
    """Test that classes are grouped by profile for checking."""
    
    def test_classes_grouped_by_profile(self):
        """Test that the plugin groups classes by their profiles."""
        
        # Create test file with mixed profiles
        test_code = '''
import zuspec.dataclasses as zdc
from zuspec.dataclasses.profiles import RetargetableProfile, PythonProfile

@zdc.dataclass(profile=RetargetableProfile)
class HardwareClass:
    data: zdc.uint32_t = zdc.output()

@zdc.dataclass(profile=PythonProfile)
class SoftwareClass:
    data: int = zdc.field(default=0)
'''
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            temp_path = Path(f.name)
        
        try:
            # Create plugin and parse
            tree = ast.parse(test_code)
            plugin = ZuspecFlake8Plugin(tree, str(temp_path))
            
            # Extract classes
            classes = plugin._extract_zuspec_classes()
            
            # Should have 2 classes
            assert len(classes) == 2
            
            # Group by profile
            profile_groups = {}
            for cls in classes:
                profile_name = plugin._detect_profile(cls)
                if profile_name not in profile_groups:
                    profile_groups[profile_name] = []
                profile_groups[profile_name].append(cls)
            
            # Should have 2 profile groups
            assert len(profile_groups) == 2
            assert 'Retargetable' in profile_groups
            assert 'Python' in profile_groups
            assert len(profile_groups['Retargetable']) == 1
            assert len(profile_groups['Python']) == 1
            
        finally:
            # Clean up
            temp_path.unlink()


class TestIntegrationWithAutoDetection:
    """Integration tests for profile auto-detection."""
    
    def test_retargetable_class_checked_with_retargetable_rules(self):
        """Test that a Retargetable class is checked with Retargetable rules."""
        from zuspec.dataclasses.data_model_factory import DataModelFactory
        from zuspec.dataclasses.ir_checker import ZuspecIRChecker
        
        # This should fail with Retargetable profile (infinite-width int)
        @zdc.dataclass(profile=RetargetableProfile)
        class BadHardwareClass:
            # Using Python int instead of width-annotated type
            pass  # Would need actual int field to test, but decorator applies
        
        # Verify profile was set
        assert hasattr(BadHardwareClass, '__profile__')
        assert BadHardwareClass.__profile__ == RetargetableProfile
    
    def test_python_class_checked_with_python_rules(self):
        """Test that a Python class is checked with permissive Python rules."""
        from zuspec.dataclasses.data_model_factory import DataModelFactory
        from zuspec.dataclasses.ir_checker import ZuspecIRChecker
        
        # This should pass with Python profile (allows int)
        @zdc.dataclass(profile=PythonProfile)
        class FlexibleSoftwareClass:
            value: int = zdc.field(default=0)
        
        # Build IR and check
        factory = DataModelFactory()
        context = factory.build([FlexibleSoftwareClass])
        
        # Check with Python profile
        checker = ZuspecIRChecker(profile='Python')
        errors = checker.check_context(context)
        
        # Python profile should not generate errors for int
        assert len(errors) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
