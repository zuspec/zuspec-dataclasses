# Zuspec IR-Based Checker

## Overview

The Zuspec IR-based checker validates Zuspec code by analyzing the Intermediate Representation (IR). This replaces the deprecated MyPy plugin with a more flexible, tool-independent approach.

## Key Features

- **Tool Independent**: Works with flake8, CLI tools, and future integrations
- **Extensible**: External packages can register custom profiles and checkers
- **Better Error Messages**: Precise locations and clear messages
- **Profile-Based**: Different validation rules for different use cases
- **Zero Configuration**: Automatic discovery via entry points

## Migration from MyPy Plugin

The MyPy plugin is **deprecated** as of version 0.0.2. Please migrate to the flake8 plugin.

### Before (MyPy Plugin)
```toml
# pyproject.toml
[tool.mypy]
plugins = ["zuspec.dataclasses.mypy.plugin"]
```

```bash
$ mypy your_file.py
```

### After (Flake8 Plugin)
```toml
# pyproject.toml - remove mypy plugin line

# .flake8 or setup.cfg
[flake8]
zuspec-profile = Retargetable
```

```bash
$ flake8 your_file.py
```

## Usage

### With Flake8 (Recommended)

The flake8 plugin is automatically enabled when you have zuspec-dataclasses installed.

**Profile Auto-Detection:**
The checker automatically detects the profile from your `@dataclass(profile=...)` declaration:

```python
import zuspec.dataclasses as zdc
from zuspec.dataclasses.profiles import RetargetableProfile, PythonProfile

@zdc.dataclass(profile=RetargetableProfile)
class HardwareComponent:
    data: zdc.uint32_t = zdc.output()  # Checked with Retargetable rules

@zdc.dataclass(profile=PythonProfile) 
class SoftwareComponent:
    data: int = zdc.field()  # Checked with Python rules (permissive)

@zdc.dataclass  # No profile specified
class DefaultComponent:
    # Uses configured default (Retargetable)
    pass
```

```bash
# Check a single file - profiles auto-detected per class
$ flake8 my_component.py

# Check entire project
$ flake8 src/

# Override default profile for classes without explicit profile
$ flake8 --zuspec-profile=Python my_file.py
```

### Configuration

Configure in `.flake8`, `setup.cfg`, or `pyproject.toml`:

```ini
[flake8]
zuspec-profile = Retargetable  # or Python, or custom
zuspec-enabled = True
```

## Built-in Profiles

### Retargetable (Default)

For code that will be compiled to hardware or other targets.

**Rules:**
- ✅ Width-annotated integers required (`uint8_t`, `uint32_t`, etc.)
- ✅ Concrete types only (no `Any` or `object`)
- ✅ Static attribute access only (no `hasattr`, `getattr`, etc.)
- ✅ All variables must be type-annotated
- ✅ Only Zuspec types in annotations
- ✅ No non-Zuspec constructors in method bodies

**Example:**
```python
import zuspec.dataclasses as zdc

@zdc.dataclass  # Uses Retargetable by default
class Counter(zdc.Component):
    count: zdc.uint32_t = zdc.output()  # ✅ OK: width-annotated
    
    @zdc.sync(clock=lambda s: s.clock)
    def _count(self):
        next_val: zdc.uint32_t = self.count + 1  # ✅ OK: annotated
        self.count = next_val
```

**Violations:**
```python
@zdc.dataclass
class BadComponent:
    count: int = zdc.field()  # ❌ ZDC001: infinite-width int
    
    def process(self):
        x = 5  # ❌ ZDC003: unannotated variable
        if hasattr(self, 'field'):  # ❌ ZDC004: dynamic access
            pass
```

### Python Profile

Permissive profile for pure-Python implementations.

**Rules:**
- ✅ Allows all Python constructs
- ✅ Infinite-width integers OK
- ✅ Dynamic attribute access OK
- ✅ Unannotated variables OK

**Example:**
```python
from zuspec.dataclasses.profiles import PythonProfile

@zdc.dataclass(profile=PythonProfile)
class FlexibleModel:
    count: int = zdc.field(default=0)  # ✅ OK in Python profile
    
    def process(self):
        x = 5  # ✅ OK: unannotated
        if hasattr(self, 'optional'):  # ✅ OK: dynamic
            return getattr(self, 'optional')
```

## Error Codes

| Code | Description |
|------|-------------|
| ZDC001 | Infinite-width int (use uint8_t, uint32_t, etc.) |
| ZDC002 | Non-Zuspec type (use Zuspec types) |
| ZDC003 | Unannotated variable (add type annotation) |
| ZDC004 | Dynamic attribute access (hasattr, getattr, etc.) |
| ZDC005 | Non-Zuspec constructor call |
| ZDC006 | Top-level function call (use Zuspec methods) |
| ZDC996-999 | Internal checker errors |

## Extensibility

External packages can register custom profiles and checkers.

### Creating a Custom Checker

**1. Implement Checker:**
```python
# mypackage/checker.py
from zuspec.dataclasses.ir_checker import BaseIRChecker, CheckError, CheckContext

class MyCustomChecker(BaseIRChecker):
    PROFILE_NAME = 'MyCustom'
    
    def check_field(self, field, check_ctx):
        errors = []
        if not field.name.islower():
            errors.append(self.make_error(
                'CUSTOM001',
                f"Field '{field.name}' must be lowercase",
                field
            ))
        return errors
```

**2. Register via Entry Points:**
```toml
# pyproject.toml
[project.entry-points."zuspec.ir_checkers"]
MyCustom = "mypackage.checker:MyCustomChecker"
```

**3. Use:**
```python
from mypackage.profile import MyCustomProfile

@zdc.dataclass(profile=MyCustomProfile)
class MyComponent:
    # Validated by MyCustomChecker
    pass
```

```bash
$ flake8 --zuspec-profile=MyCustom my_file.py
```

## API Reference

### ZuspecIRChecker

Main orchestrator for IR checking.

```python
from zuspec.dataclasses.ir_checker import ZuspecIRChecker
from zuspec.dataclasses.data_model_factory import DataModelFactory

# Build IR
factory = DataModelFactory()
context = factory.build([MyClass])

# Check
checker = ZuspecIRChecker(profile='Retargetable')
errors = checker.check_context(context)

# Report
for error in errors:
    print(f"{error.filename}:{error.lineno}: {error.code}: {error.message}")
```

### CheckerRegistry

Registry for managing checkers.

```python
from zuspec.dataclasses.ir_checker import CheckerRegistry

# List available profiles
profiles = CheckerRegistry.list_profiles()
# ['Python', 'Retargetable', ...]

# Get checker for a profile
checker_cls = CheckerRegistry.get_checker('Retargetable')

# Manual registration (alternative to entry points)
CheckerRegistry.register(MyChecker, 'MyProfile')
```

### BaseIRChecker

Base class for custom checkers.

```python
from zuspec.dataclasses.ir_checker import BaseIRChecker

class MyChecker(BaseIRChecker):
    PROFILE_NAME = 'MyProfile'
    
    def check_field(self, field, check_ctx):
        # Your validation logic
        return []
    
    def check_function(self, func, check_ctx):
        # Your validation logic
        return []
```

## Architecture

```
User Code (Python)
    ↓
DataModelFactory
    ↓
IR (Context, DataType, Field, Function, Expr, Stmt)
    ↓
ZuspecIRChecker (orchestrator)
    ↓
ProfileChecker (Retargetable, Python, Custom)
    ↓
CheckError (code, message, location)
    ↓
Reporting (flake8, CLI, IDE)
```

## Benefits Over MyPy Plugin

1. **Tool Independence**: Works with flake8, not just MyPy
2. **Better Errors**: Precise locations, clear messages
3. **Extensibility**: Easy to add custom profiles
4. **Stability**: Independent of MyPy's release cycle
5. **Reusability**: Same checker for multiple tools
6. **Testability**: Easier to test than MyPy plugin

## FAQ

**Q: Can I still use the MyPy plugin?**  
A: Yes, but it's deprecated and will be removed in a future version. Please migrate to flake8.

**Q: Does flake8 replace MyPy for type checking?**  
A: No. Use MyPy for type checking and flake8 for Zuspec validation. They complement each other.

**Q: Can I use both MyPy and flake8 plugins?**  
A: The MyPy plugin is deprecated and does nothing. Use only flake8.

**Q: How do I run checks in CI/CD?**  
A: Add `flake8` to your CI pipeline:
```yaml
# .github/workflows/ci.yml
- name: Check Zuspec code
  run: flake8 src/
```

**Q: Can I disable Zuspec checking for a file?**  
A: Yes, add to the file:
```python
# flake8: noqa: ZDC
```

Or in configuration:
```ini
[flake8]
zuspec-enabled = False
```

## Support

- **Documentation**: See `docs/` directory
- **Examples**: See `examples/` directory
- **Issues**: https://github.com/yourusername/zuspec-dataclasses/issues

## License

Apache License 2.0
