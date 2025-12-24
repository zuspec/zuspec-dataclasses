"""Test file for Retargetable profile - demonstrates errors that should be caught."""
import zuspec.dataclasses as zdc
from zuspec.dataclasses import profiles


# This should produce MyPy error: infinite-width int not allowed
@zdc.dataclass(profile=profiles.RetargetableProfile)
class BadCounter:
    count: int = zdc.field(default=0)  # error: infinite-width 'int'


# This should be OK: width-annotated types
@zdc.dataclass(profile=profiles.RetargetableProfile)
class GoodCounter:
    count: zdc.uint32_t = zdc.field(default=0)


# This should produce MyPy error: unannotated variable
@zdc.dataclass(profile=profiles.RetargetableProfile)
class BadProcessor(zdc.Component):
    value: zdc.uint32_t = zdc.output()
    
    @zdc.process
    async def _process(self):
        x = 5  # error: Variable not type-annotated
        self.value = x


# This should be OK: annotated variable
@zdc.dataclass(profile=profiles.RetargetableProfile)
class GoodProcessor(zdc.Component):
    value: zdc.uint32_t = zdc.output()
    
    @zdc.process
    async def _process(self):
        x: zdc.uint32_t = 5
        self.value = x


# This should produce MyPy error: dynamic attribute access not allowed
@zdc.dataclass(profile=profiles.RetargetableProfile)
class BadDynamic:
    
    def check(self):
        if hasattr(self, 'field'):  # error: Name-based manipulation not allowed
            return getattr(self, 'field')  # error: Name-based manipulation not allowed


# Default should be Retargetable
@zdc.dataclass
class DefaultCounter:
    # Should require width-annotated type
    count: zdc.uint32_t = zdc.field(default=0)
