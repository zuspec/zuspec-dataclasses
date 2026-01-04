# Documentation Updates for IR Checker

## Summary

Updated zuspec-dataclasses documentation to reflect the new flake8-based IR checker and deprecate the old mypy-based approach.

## Files Created

### 1. `docs/checker.rst` (NEW)

**Comprehensive documentation for the IR Checker system:**

- **Overview** - Architecture and key features
- **Installation and Setup** - Including VSCode integration
- **Error Codes** - Complete reference (ZDC001-ZDC006) with examples
- **Built-in Profiles** - PythonProfile and RetargetableProfile
- **Profile Auto-Detection** - How profiles are determined
- **Creating Custom Checkers** - Step-by-step guide with examples
- **Checker Extension API** - ProfileChecker base class and utilities
- **Command-Line Usage** - Running from terminal and CI/CD
- **Troubleshooting** - Common issues and solutions
- **Comparison with Other Tools** - vs MyPy, flake8, PyLint
- **FAQ** - Frequently asked questions

## Files Modified

### 2. `docs/index.rst`

**Changes:**

1. Updated Quick Links to feature the new checker
2. Added checker to User Guide table of contents
3. Reorganized additional documentation with deprecation notice

### 3. `docs/profile_checker_guide.md`

**Added deprecation warning** directing users to the new IR checker documentation.

### 4. `docs/profile_checker_design.md`

**Added deprecation warning** explaining the architectural changes in the new IR-based checker.

## Documentation Structure

```
docs/
├── index.rst                          # Main index - UPDATED
│   ├── User Guide
│   │   ├── intro.rst
│   │   ├── components.rst
│   │   ├── fields.rst
│   │   ├── types.rst
│   │   ├── runtime.rst
│   │   ├── abstraction_levels.rst
│   │   └── checker.rst                # NEW - IR Checker docs
│   ├── Advanced Topics
│   │   ├── datamodel.rst
│   │   └── profiles.rst
│   └── Historical (Deprecated)
│       ├── profile_checker_guide.md   # DEPRECATED - Added warning
│       └── profile_checker_design.md  # DEPRECATED - Added warning
```

## Key Improvements

### 1. **Centralized Documentation**

All checker information is now in one comprehensive document (`checker.rst`).

### 2. **Clear Deprecation Path**

The old mypy-based documentation is clearly marked as deprecated with warning boxes and links to new docs.

### 3. **Practical Examples**

Every error code includes "Bad" and "Good" examples showing the error and fix.

### 4. **VSCode Integration**

Detailed setup instructions for VSCode with step-by-step configuration.

### 5. **Extensibility Focus**

Comprehensive guide for creating custom checkers with entrypoint registration.

### 6. **Troubleshooting Section**

Common issues and solutions including source location problems and VSCode integration.

## Building the Documentation

To build the HTML documentation:

```bash
cd packages/zuspec-dataclasses/docs
make html
# Output in _build/html/index.html
```

## Version Information

- **Documentation Version:** 2026.1 (January 2026)
- **IR Checker:** Introduced in version 2026.1
- **MyPy Plugin:** Deprecated in version 2026.1
- **Source Location Fix:** Included in version 2026.1

The documentation is now ready for users to successfully install, configure, and use the Zuspec IR Checker! 📚✨
