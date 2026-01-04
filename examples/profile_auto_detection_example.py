"""
Example demonstrating profile auto-detection in zuspec-dataclasses.

This file shows how different classes can use different profiles,
and the flake8 plugin automatically detects and applies the correct
validation rules for each class.
"""

import zuspec.dataclasses as zdc
from zuspec.dataclasses.profiles import RetargetableProfile, PythonProfile


# Example 1: Hardware component with Retargetable profile
@zdc.dataclass(profile=RetargetableProfile)
class HardwareCounter(zdc.Component):
    """
    Hardware component - must follow strict rules:
    - Width-annotated integers required
    - All variables must be type-annotated
    - No dynamic attribute access
    """
    count: zdc.uint32_t = zdc.output()
    enable: zdc.bit = zdc.input()
    
    @zdc.sync(clock=lambda s: s.clock)
    def _count(self):
        # ✅ OK: variable is type-annotated
        next_val: zdc.uint32_t = self.count + 1
        if self.enable:
            self.count = next_val


# Example 2: Software model with Python profile
@zdc.dataclass(profile=PythonProfile)
class SoftwareModel:
    """
    Pure Python model - permissive rules:
    - Infinite-width int allowed
    - Unannotated variables OK
    - Dynamic attribute access allowed
    """
    count: int = zdc.field(default=0)  # ✅ OK: int allowed in Python profile
    
    def increment(self):
        # ✅ OK: unannotated variable in Python profile
        x = 1
        self.count += x
        
        # ✅ OK: dynamic access in Python profile
        if hasattr(self, 'max_count'):
            if self.count >= self.max_count:
                self.count = 0


# Example 3: Default profile (uses Retargetable)
@zdc.dataclass
class DefaultComponent:
    """
    No profile specified - uses configured default (Retargetable).
    
    This will be checked with Retargetable rules.
    """
    data: zdc.uint32_t = zdc.field(default=0)  # ✅ OK: width-annotated


# Example 4: Mixed profiles demonstrate per-class validation
@zdc.dataclass(profile=PythonProfile)
class FlexibleProcessor:
    """Python profile: allows any Python construct."""
    state: dict = zdc.field(default_factory=dict)
    
    def process(self, data):
        # All of this is OK in Python profile
        temp = data * 2
        self.state[temp] = data
        return getattr(self, 'result', None)


@zdc.dataclass(profile=RetargetableProfile)
class StrictProcessor(zdc.Component):
    """Retargetable profile: enforces hardware-compatible rules."""
    state: zdc.uint32_t = zdc.field(default=0)
    
    @zdc.comb
    def process(self, data: zdc.uint32_t) -> zdc.uint32_t:
        # Must follow strict rules
        temp: zdc.uint32_t = data * 2  # ✅ Type annotation required
        result: zdc.uint32_t = temp + self.state
        return result


# Flake8 will automatically:
# 1. Detect RetargetableProfile for HardwareCounter, StrictProcessor, DefaultComponent
# 2. Detect PythonProfile for SoftwareModel, FlexibleProcessor
# 3. Apply appropriate validation rules to each class
# 4. Report errors only for violations in each profile

# Run with:
#   $ flake8 profile_auto_detection_example.py
#
# The plugin will check each class with its declared profile,
# allowing mixed profiles in the same file!
