"""
Verification test for profile checker MyPy integration.

This file deliberately contains violations to demonstrate that the
profile checker catches them.
"""
import zuspec.dataclasses as zdc
from zuspec.dataclasses import profiles


# Test 1: RetargetableProfile should catch infinite-width int
print("Test 1: Infinite-width int violation")
try:
    @zdc.dataclass  # Uses RetargetableProfile by default
    class BadCounter1:
        # MyPy should error: Field 'count' uses infinite-width 'int'
        count: int = zdc.field(default=0)
    
    # This will run at runtime, but MyPy should flag it
    c1 = BadCounter1()
    print(f"  Runtime: count={c1.count} (MyPy should have caught this)")
except Exception as e:
    print(f"  Error: {e}")


# Test 2: RetargetableProfile allows width-annotated types
print("\nTest 2: Width-annotated types (should be OK)")
try:
    @zdc.dataclass
    class GoodCounter:
        count: zdc.uint32_t = zdc.field(default=0)
    
    c2 = GoodCounter()
    print(f"  ✓ Runtime: count={c2.count}")
except Exception as e:
    print(f"  Error: {e}")


# Test 3: PythonProfile allows infinite-width int
print("\nTest 3: PythonProfile allows int")
try:
    @zdc.dataclass(profile=profiles.PythonProfile)
    class FlexibleCounter:
        count: int = zdc.field(default=0)
    
    c3 = FlexibleCounter()
    print(f"  ✓ Runtime: count={c3.count}")
except Exception as e:
    print(f"  Error: {e}")


# Test 4: RetargetableProfile should catch unannotated variables
print("\nTest 4: Unannotated variable violation")
try:
    @zdc.dataclass
    class BadProcessor(zdc.Component):
        value: zdc.uint32_t = zdc.output()
        
        @zdc.process
        async def _process(self):
            # MyPy should error: Variable 'x' is not type-annotated
            x = 5
            self.value = x
    
    # This will run at runtime, but MyPy should flag it
    c4 = BadProcessor()
    print(f"  Runtime: value={c4.value} (MyPy should have caught unannotated 'x')")
except Exception as e:
    print(f"  Error: {e}")


# Test 5: RetargetableProfile allows annotated variables
print("\nTest 5: Annotated variables (should be OK)")
try:
    @zdc.dataclass
    class GoodProcessor(zdc.Component):
        value: zdc.uint32_t = zdc.output()
        
        @zdc.process
        async def _process(self):
            x: zdc.uint32_t = 5
            self.value = x
    
    c5 = GoodProcessor()
    print(f"  ✓ Runtime: value={c5.value}")
except Exception as e:
    print(f"  Error: {e}")


print("\n" + "="*70)
print("Runtime execution completed.")
print("\nTo see MyPy profile checking, run:")
print("  mypy --config-file packages/zuspec-dataclasses/pyproject.toml \\")
print("       tests/unit/mypy_tests/test_violations.py")
print("\nExpected MyPy errors:")
print("  - Test 1: infinite-width int")
print("  - Test 4: unannotated variable")
print("="*70)
