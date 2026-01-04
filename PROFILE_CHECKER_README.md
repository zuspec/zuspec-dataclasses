# Profile Checker System

The zuspec-dataclasses profile checker system enables extensible, profile-specific validation of dataclasses at MyPy type-check time.

## Quick Start

### Using Built-in Profiles

```python
import zuspec.dataclasses as zdc
from zuspec.dataclasses import profiles

# Python Profile - Permissive (allows any Python)
@zdc.dataclass(profile=profiles.PythonProfile)
class FlexibleModel:
    count: int = zdc.field(default=0)  # infinite-width int OK

# Retargetable Profile - Default (strict, hardware-targetable)
@zdc.dataclass  # or explicit: profile=profiles.RetargetableProfile
class HardwareModel(zdc.Component):
    count: zdc.uint32_t = zdc.output()  # width-annotated required
```

### Creating Custom Profiles

```python
from zuspec.dataclasses.profiles import Profile, PROFILE_REGISTRY

class MyChecker:
    def check_field_type(self, field_name, field_type, ctx):
        # Your validation logic
        pass

class MyProfile(Profile):
    @classmethod
    def get_checker(cls):
        return MyChecker()  # type: ignore

# Use it
@zdc.dataclass(profile=MyProfile)
class MyClass:
    pass
```

## Documentation

- **[User Guide](docs/profile_checker_guide.md)** - Complete usage documentation
- **[Design Document](docs/profile_checker_design.md)** - Implementation details
- **[Profiles Overview](docs/profiles.md)** - Design abstraction levels
- **[Example Code](../examples/profile_example.py)** - Working examples

## Built-in Profiles

| Profile | Description | Use Case |
|---------|-------------|----------|
| `PythonProfile` | Permissive, allows all Python | Prototyping, pure Python code |
| `RetargetableProfile` | Strict, hardware-targetable | Default, synthesis/compilation |
| `ZuspecFull` | Alias for Retargetable | Same as Retargetable |

## Features

- ✅ Extensible profile system
- ✅ MyPy integration for type-check time validation
- ✅ Custom checker interface
- ✅ Built-in Python and Retargetable profiles
- ✅ Clear, actionable error messages
- ✅ Profile registry for discoverability

## MyPy Configuration

Add to your `pyproject.toml`:

```toml
[tool.mypy]
plugins = ["zuspec.dataclasses.mypy.plugin"]
```

## Examples

See `examples/profile_example.py` for a complete working example demonstrating:
1. Using PythonProfile for flexible code
2. Using RetargetableProfile (default) for hardware-targetable code
3. Creating and using a custom RestrictedRTL profile

Run the example:
```bash
python examples/profile_example.py
```

Check with MyPy:
```bash
mypy --config-file packages/zuspec-dataclasses/pyproject.toml examples/profile_example.py
```

## Testing

Run the profile tests:
```bash
pytest tests/unit/test_profiles.py
```

Test MyPy plugin:
```bash
python tests/unit/test_mypy_plugin.py
```
