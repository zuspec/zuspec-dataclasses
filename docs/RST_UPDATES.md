# Documentation Updates - Constraint Solver Features

## Date: 2026-02-14

## Summary
Updated `constraints.rst` to reflect new constraint solver features implemented:
- Fixed-size arrays with indexing
- Iterative constraints (for loops)
- Constraint helper functions (sum, unique, ascending, descending)
- Inline constraints with randomize_with
- Updated syntax (domain instead of bounds, assert statements)

## Changes Made

### Quick Example (Lines 1-60)
- Added import of `List` from typing
- Showcased array field with `List[int]`
- Demonstrated helper functions (unique, sum)
- Showed iterative constraints with for loops
- Used new `domain` parameter instead of `bounds`
- Removed `default` parameters (not required)

### Random Variables Section (Lines 62-120)
- Split into **Scalar Fields** and **Array Fields** subsections
- Updated parameter name from `bounds` to `domain`
- Added comprehensive array examples
- Removed `default` parameter references
- Added note about parameter naming change
- Clarified `size` parameter for arrays

### Constraint Decorators Section (Lines 122-160)
- Added `assert` statement syntax throughout
- Updated all examples to use `assert`
- Clarified multiple assertions are ANDed

### NEW: Array Constraints Section (Lines 162-260)
Added comprehensive new section covering:
- **Array Declaration** - Fixed-size arrays with List[T]
- **Array Indexing** - Subscript notation for elements
- **Computed Indices** - Arithmetic in indices (i+1, i*3)
- **Iterative Constraints** - For loops over arrays
  - Simple loops
  - Nested loops
  - Variable-bounded loops
  - Using len()
- Note about parse-time expansion

### Helper Functions Section (Lines 380-490)
Completely rewritten with new helpers:
- **sum()** - Array summation (NEW)
  - Usage in expressions
  - Expansion details
  - Examples
- **unique()** - Uniqueness constraint (UPDATED)
  - Now supports arrays
  - Expansion to nested loops
  - Use cases
- **ascending()** - Strictly ascending order (NEW)
  - Expansion details
  - Use cases
- **descending()** - Strictly descending order (NEW)
  - Expansion details
  - Use cases
- **Combining Helpers** - Multiple helpers in one constraint
- **implies()** - Moved down, updated syntax with assert
- **dist()** - Updated syntax
- Removed duplicate `unique()` section for scalars
- **solve_order()** - Updated syntax

### NEW: Inline Constraints Section (Lines 625-710)
Added comprehensive randomize_with documentation:
- **Basic Usage** - Simple inline constraints
- **With Loops** - Iterative inline constraints
- **With Helper Functions** - Using sum, unique, etc.
- **With Seed** - Reproducible randomization
- **Combining with Class Constraints** - How inline and class constraints interact

### Constraint Expressions Section (Lines 320-385)
- Added `assert` statements to all examples
- Updated syntax throughout

### Complete Example (Lines 758-820)
Completely rewritten to showcase:
- Array fields (header, payload)
- Helper functions (unique, sum, implies)
- Iterative constraints (for loop)
- randomize_with usage
- New domain parameter
- Removed outdated ConstraintParser usage
- Practical network packet example

### Supported Patterns Section (Lines 822-850)
Updated feature status:
- ✅ Array constraints (was ⏳)
- ✅ Iterative constraints with for loops (was ⏳)
- ✅ Helper functions sum/unique/ascending/descending (NEW)
- ✅ Inline constraints with randomize_with (NEW)
- Added new future items (variable-size arrays, jagged arrays)

### Design Notes Section (Lines 870-895)
- Updated statement syntax examples to use `assert`
- Added variable-size arrays to future extensions
- Added additional helpers to future extensions
- Removed "array constraints" from future (now complete)

## Statistics
- **Lines changed**: ~400 lines updated/added
- **New sections**: 2 (Array Constraints, Inline Constraints)
- **Rewritten sections**: 4 (Helper Functions, Complete Example, Quick Example, Supported Patterns)
- **Examples updated**: All examples now use assert syntax and domain parameter

## Testing
All examples in the documentation reflect actual working features:
- 454 total tests passing
- 25 new tests for helper functions
- All demos (demo_constraint_helpers.py, demo_iterative_constraints.py, demo_array_phase1a.py) working

## Compatibility
- Old `bounds` parameter still supported (backward compatible)
- Statement syntax without `assert` still works in many contexts
- Documentation reflects recommended/modern syntax

## Next Steps
- [ ] Update intro.rst if it references constraints
- [ ] Update index.rst to highlight new features
- [ ] Consider adding a "Quick Reference" or "Cheat Sheet" page
- [ ] Add migration guide for bounds → domain
