"""Test enhanced RetargetableProfile checking for dynamic access and non-Zuspec types."""
import zuspec.dataclasses as zdc
from zuspec.dataclasses import profiles


# Define a non-Zuspec class
class NonZuspecClass:
    pass


# Test 1: Dynamic attribute access should be flagged
@zdc.dataclass
class TestDynamicAccess(zdc.Component):
    value: zdc.uint32_t = zdc.field(default=0)
    
    def check_with_getattr(self):
        # error: Dynamic attribute access ('getattr') not allowed
        return getattr(self, 'value')
    
    def check_with_hasattr(self):
        # error: Dynamic attribute access ('hasattr') not allowed
        if hasattr(self, 'optional_field'):
            return True
        return False
    
    def check_with_setattr(self):
        # error: Dynamic attribute access ('setattr') not allowed
        setattr(self, 'value', 10)


# Test 2: Non-Zuspec types in parameters should be flagged
@zdc.dataclass
class TestNonZuspecParam(zdc.Component):
    value: zdc.uint32_t = zdc.field(default=0)
    
    # error: Parameter 'obj' has non-Zuspec type
    def process_object(self, obj: NonZuspecClass):
        pass


# Test 3: Non-Zuspec types in fields should be flagged
@zdc.dataclass
class TestNonZuspecField(zdc.Component):
    value: zdc.uint32_t = zdc.field(default=0)
    # error: Field 'obj' has non-Zuspec type
    obj: NonZuspecClass = zdc.field()


# Test 4: Zuspec types should be allowed
@zdc.dataclass
class GoodZuspecTypes(zdc.Component):
    # These should all be OK
    val1: zdc.uint32_t = zdc.field(default=0)
    val2: zdc.uint8_t = zdc.field(default=0)
    val3: str = zdc.field(default="")
    val4: bool = zdc.field(default=False)
    
    def process_zuspec_type(self, other: 'GoodZuspecTypes'):
        # This should be OK - GoodZuspecTypes is Zuspec-derived
        pass


# Test 5: Python profile should allow everything
@zdc.dataclass(profile=profiles.PythonProfile)
class PythonProfileAllows:
    value: int = zdc.field(default=0)  # OK with Python profile
    obj: NonZuspecClass = zdc.field()  # OK with Python profile
    
    def use_dynamic_access(self):
        # OK with Python profile
        return getattr(self, 'value')
    
    def accept_non_zuspec(self, obj: NonZuspecClass):
        # OK with Python profile
        pass


if __name__ == '__main__':
    print("This file is meant to be checked with MyPy.")
    print("Run: mypy --config-file packages/zuspec-dataclasses/pyproject.toml tests/unit/mypy_tests/test_enhanced_checks.py")
