"""Test file for Python profile - should pass mypy without errors."""
import zuspec.dataclasses as zdc
from zuspec.dataclasses import profiles


@zdc.dataclass(profile=profiles.PythonProfile)
class FlexibleCounter:
    """Python profile allows infinite-width int."""
    count: int = zdc.field(default=0)
    data: dict = zdc.field(default_factory=dict)
    
    def increment(self):
        # Unannotated variables are OK in Python profile
        step = 1
        self.count += step
    
    def check_value(self):
        # Dynamic attribute access is OK in Python profile
        if hasattr(self, 'optional_field'):
            return getattr(self, 'optional_field')
        return None


@zdc.dataclass(profile=profiles.PythonProfile)
class DynamicModel:
    """Python profile allows dynamic operations."""
    
    def __init__(self):
        self.fields = {}
    
    def set_field(self, name: str, value):
        # setattr is OK in Python profile
        setattr(self, name, value)
    
    def get_field(self, name: str):
        # getattr is OK in Python profile
        return getattr(self, name, None)


if __name__ == '__main__':
    counter = FlexibleCounter()
    counter.increment()
    print(f"Count: {counter.count}")
