# Profile Auto-Detection Feature

## Overview

The Zuspec IR checker now **automatically detects** the validation profile from each class's `@dataclass(profile=...)` decorator. This allows:

- **Mixed profiles in the same file** - Hardware and software classes coexist
- **Per-class validation** - Each class checked with its appropriate rules
- **Zero configuration** - No need to specify profile on command line
- **Flexible development** - Use strict rules where needed, permissive elsewhere

## How It Works

### 1. Profile Declaration

The `@dataclass` decorator stores the profile in the class's `__profile__` attribute:

```python
import zuspec.dataclasses as zdc
from zuspec.dataclasses.profiles import RetargetableProfile, PythonProfile

@zdc.dataclass(profile=RetargetableProfile)
class HardwareClass:
    data: zdc.uint32_t = zdc.output()

@zdc.dataclass(profile=PythonProfile)
class SoftwareClass:
    data: int = zdc.field()
```

After decoration:
- `HardwareClass.__profile__` = `RetargetableProfile`
- `SoftwareClass.__profile__` = `PythonProfile`

### 2. Profile Detection

The flake8 plugin detects profiles in `_detect_profile()`:

```python
def _detect_profile(self, cls: type) -> str:
    if hasattr(cls, '__profile__'):
        profile_cls = cls.__profile__
        return profile_cls.get_name()  # Returns 'Retargetable' or 'Python'
    return self.zuspec_profile  # Default from config
```

### 3. Grouping and Checking

Classes are grouped by profile and checked separately:

```python
# Group classes by profile
profile_groups = {
    'Retargetable': [HardwareClass],
    'Python': [SoftwareClass]
}

# Check each group with appropriate checker
for profile_name, classes in profile_groups.items():
    checker = ZuspecIRChecker(profile=profile_name)
    errors = checker.check_context(...)
```

## Usage Examples

### Example 1: Mixed Profiles in Same File

```python
# my_module.py
import zuspec.dataclasses as zdc
from zuspec.dataclasses.profiles import RetargetableProfile, PythonProfile

@zdc.dataclass(profile=RetargetableProfile)
class HardwareCounter:
    count: zdc.uint32_t = zdc.output()  # ✅ Width-annotated
    
    @zdc.sync(clock=lambda s: s.clock)
    def _count(self):
        next: zdc.uint32_t = self.count + 1  # ✅ Type-annotated
        self.count = next

@zdc.dataclass(profile=PythonProfile)
class SoftwareModel:
    count: int = zdc.field(default=0)  # ✅ OK in Python profile
    
    def increment(self):
        x = 1  # ✅ Unannotated OK in Python profile
        self.count += x
```

```bash
$ flake8 my_module.py
# No errors! Each class checked with its declared profile
```

### Example 2: Violations Detected Per Profile

```python
# bad_mixed.py
@zdc.dataclass(profile=RetargetableProfile)
class BadHardware:
    count: int = zdc.field()  # ❌ ZDC001: infinite-width int
    
    def process(self):
        x = 5  # ❌ ZDC003: unannotated variable
        if hasattr(self, 'data'):  # ❌ ZDC004: dynamic access
            pass

@zdc.dataclass(profile=PythonProfile)
class GoodSoftware:
    count: int = zdc.field()  # ✅ OK in Python profile
    
    def process(self):
        x = 5  # ✅ OK in Python profile
        if hasattr(self, 'data'):  # ✅ OK in Python profile
            pass
```

```bash
$ flake8 bad_mixed.py
bad_mixed.py:3:5: ZDC001 Field 'count' uses infinite-width int
bad_mixed.py:6:9: ZDC003 Variable 'x' is not type-annotated
bad_mixed.py:7:12: ZDC004 Dynamic attribute access ('hasattr') is not allowed
# No errors for GoodSoftware - Python profile is permissive
```

### Example 3: Default Profile

```python
# When no profile specified, uses configured default

@zdc.dataclass  # No profile parameter
class DefaultClass:
    data: zdc.uint32_t = zdc.field()
```

```bash
# Uses default from config (usually Retargetable)
$ flake8 my_file.py

# Or specify default via config
$ flake8 --zuspec-profile=Python my_file.py
```

## Configuration

### Per-File Profiles

Profiles are detected from each class, so no configuration needed.

### Default Profile

For classes without explicit profile:

```ini
# .flake8
[flake8]
zuspec-profile = Retargetable  # Default for classes without profile=...
```

```bash
# Or command line
$ flake8 --zuspec-profile=Python my_file.py
```

## Implementation Details

### Profile Classes

Profile classes must implement `get_name()`:

```python
class RetargetableProfile(Profile):
    @classmethod
    def get_name(cls) -> str:
        return 'Retargetable'  # Without 'Profile' suffix

class PythonProfile(Profile):
    @classmethod
    def get_name(cls) -> str:
        return 'Python'
```

### Decorator Storage

The `@dataclass` decorator stores the profile:

```python
def dataclass(cls=None, *, profile=None, **kwargs):
    def decorator(cls):
        if profile is not None:
            cls.__profile__ = profile  # Stored here
        cls_t = dc.dataclass(cls, kw_only=True, **kwargs)
        return cls_t
    # ...
```

### Flake8 Plugin Flow

```
1. Extract classes from file
2. For each class:
   a. Check __profile__ attribute
   b. Call profile.get_name()
   c. Group by profile name
3. For each profile group:
   a. Build IR from group's classes
   b. Create checker for profile
   c. Run checker
   d. Collect errors
4. Report all errors
```

## Benefits

### ✅ Flexibility
- Mix hardware and software components in same file
- Use strict rules only where needed
- Gradual migration (add profiles incrementally)

### ✅ Clarity
- Profile is visible in code (`@dataclass(profile=...)`)
- No hidden configuration files
- Clear intent for each class

### ✅ Correctness
- Right rules for right code
- No false positives from wrong profile
- Hardware code properly validated

### ✅ Maintainability
- Easy to change profile for a class
- Profiles documented in code
- No global configuration to remember

## Testing

All tests pass (19 tests):

```bash
$ pytest tests/unit/test_profile_detection.py -v
...
test_detect_retargetable_profile PASSED
test_detect_python_profile PASSED
test_detect_default_profile_when_not_specified PASSED
test_mixed_profiles_in_same_file PASSED
test_profile_stored_in_class_attribute PASSED
test_classes_grouped_by_profile PASSED
...
```

## Migration from Command-Line Profile

### Before (Global Profile)
```bash
# All classes checked with same profile
$ flake8 --zuspec-profile=Retargetable my_file.py
```

### After (Auto-Detection)
```python
# Each class declares its profile
@zdc.dataclass(profile=RetargetableProfile)
class Hardware: ...

@zdc.dataclass(profile=PythonProfile)
class Software: ...
```

```bash
# Profiles auto-detected
$ flake8 my_file.py
```

## FAQ

**Q: What if I don't specify a profile?**  
A: Uses the configured default (usually Retargetable).

**Q: Can I override auto-detection?**  
A: The `--zuspec-profile` flag only sets the default for classes without explicit profile.

**Q: Can I have multiple profiles in one file?**  
A: Yes! That's the whole point. Each class is checked with its declared profile.

**Q: Does this work with external profiles?**  
A: Yes, external packages can register custom profiles via entry points.

**Q: What about performance?**  
A: Classes are grouped by profile, so each profile's checker runs once.

## See Also

- `IR_CHECKER_README.md` - Full user documentation
- `examples/profile_auto_detection_example.py` - Complete example
- `tests/unit/test_profile_detection.py` - Test suite
