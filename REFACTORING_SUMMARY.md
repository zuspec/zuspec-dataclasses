# Zuspec Unified Terminology Refactoring

## Overview
This refactoring unifies terminology across the Zuspec codebase to remove RTL-specific references and use consistent naming that reflects the framework's broader applicability beyond hardware design.

## Key Changes

### 1. File Renaming
The following files were renamed to use generic terminology:

| Old Name | New Name | Purpose |
|----------|----------|---------|
| `rtl_state.py` | `eval_state.py` | State management for evaluation |
| `rtl_executor.py` | `executor.py` | Process execution engine |
| `rtl_simulator.py` | `simulator.py` | Orchestrates sync/comb process execution |

### 2. Class Renaming
Classes were renamed to remove RTL-specific references:

| Old Name | New Name |
|----------|----------|
| `RTLState` | `EvalState` |
| `RTLExecutor` | `Executor` |
| `RTLSimulator` | `Simulator` |

### 3. Method Renaming in `CompImplRT`
Methods were renamed for consistency:

| Old Name | New Name |
|----------|----------|
| `rtl_signal_write()` | `signal_write()` |
| `rtl_signal_read()` | `signal_read()` |
| `rtl_set_input()` | `set_input()` |
| `rtl_get_output()` | `get_output()` |
| `rtl_clock_edge()` | `clock_edge()` |
| `rtl_eval_comb()` | `eval_comb()` |
| `_init_rtl()` | `_init_eval()` |
| `_initialize_rtl_state()` | `_initialize_eval_state()` |
| `_execute_rtl_function()` | `_execute_function()` |

### 4. Field Renaming in `CompImplRT`
Internal fields were renamed to use generic terminology:

| Old Name | New Name |
|----------|----------|
| `_rtl_mode` | `_eval_mode` |
| `_rtl_signal_values` | `_signal_values` |
| `_rtl_deferred_writes` | `_deferred_writes` |
| `_rtl_sensitivity` | `_sensitivity` |
| `_rtl_sync_processes` | `_sync_processes` |
| `_rtl_comb_processes` | `_comb_processes` |
| `_rtl_initialized` | `_eval_initialized` |
| `_rtl_pending_eval` | `_pending_eval` |
| `_rtl_state` | `_eval_state` |
| `_rtl_datamodel` | `_datamodel` |

### 5. Method Renaming in `DataModelFactory`
| Old Name | New Name |
|----------|----------|
| `_validate_rtl_bind()` | `_validate_bind()` |

### 6. Documentation Updates
All comments and docstrings were updated to:
- Remove references to "RTL" 
- Use "sync/comb processes" instead of "RTL processes"
- Use "evaluation" instead of "RTL simulation"
- Use "component with sync/comb processes" instead of "RTL component"
- Keep references to hardware concepts (clock edges, signals, deferred assignment) as they are part of the modeling semantics

### 7. Variable Name Updates
Throughout the codebase:
- `use_rtl_state` → `use_eval_state`
- `has_rtl` → `has_eval`
- References to "RTL" in variable names were changed to more generic terms

## Test Updates

All test files were updated:
- `test_rtl_state.py`: Test function names changed from `test_rtl_state_*` to `test_eval_state_*`
- `test_rtl_execution.py`: Updated imports to use `Simulator` instead of `RTLSimulator`
- `test_rtl_binding.py`: Updated comments to reference "sync/comb processes" instead of "RTL"
- `test_rtl_datamodel.py`: Updated documentation strings
- `test_rtl.py`: Updated documentation strings

All 94 unit tests pass successfully after the refactoring.

## Key Principles

1. **Unified Naming**: All components use the same terminology regardless of whether they model hardware, software, or system behavior
2. **Semantic Preservation**: Hardware-specific concepts (clock edges, deferred assignment, combinational logic) are retained as they describe the evaluation semantics
3. **Zuspec-Centric**: The terminology emphasizes that this is Zuspec with different evaluation modes, not different languages
4. **Consistency**: Method and variable names follow a consistent pattern across all modules

## Backward Compatibility

This is a breaking change for code that directly references:
- The old file names in imports
- The old class names `RTLState`, `RTLExecutor`, `RTLSimulator`
- The old method names on `CompImplRT`

However, user-facing APIs (`@sync`, `@comb`, `input()`, `output()`) remain unchanged.

## Benefits

1. **Clarity**: The code now clearly expresses that Zuspec is a unified framework
2. **Maintainability**: Consistent naming makes the codebase easier to understand
3. **Extensibility**: Generic terminology makes it easier to add new evaluation modes
4. **Documentation**: Comments and docstrings accurately describe what the code does without implying RTL-only usage
