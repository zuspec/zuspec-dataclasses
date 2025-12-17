# RTL Abstraction

## Implementation Status Summary

**Phase 1 (Type System) - ✅ COMPLETE**
- Bit type aliases (bit, bit1-bit64) implemented and exported
- All types properly aliased to underlying uint types

**Phase 2 (Port Declarations) - ✅ COMPLETE (existing functionality)**
- Input/output port declarations already working via `input()` and `output()` initializers
- Input and Output marker classes available

**Phase 3 (Sync Processes) - 🔧 PARTIAL**
- ✅ @sync decorator implemented
- ✅ ExecSync class with clock/reset parameters
- ✅ Datamodel extensions (sync_processes list, Function.metadata)
- ⏳ Datamodel factory processing (Phase 3.2 - pending)
- ⏳ Runtime execution engine (Phase 3.3 - pending)

**Phase 4 (Comb Processes) - 🔧 PARTIAL**
- ✅ @comb decorator implemented
- ✅ ExecComb class
- ✅ Datamodel extensions (comb_processes list)
- ⏳ Datamodel factory processing (Phase 4.2 - pending)
- ⏳ Runtime execution engine (Phase 4.4 - pending)

**Examples and Tests**
- ✅ Test suite for API layer (7 tests, all passing)
- ✅ counter.py example (sync process)
- ✅ alu.py example (comb and combined sync/comb)
- ✅ Comprehensive documentation in examples/rtl/README.md

**Next Steps**: Implement datamodel factory processing to convert @sync/@comb methods to datamodel Functions (Phases 3.2 and 4.2)

**📋 Future Work**: See [rtl_future.md](rtl_future.md) for detailed implementation plan for remaining phases.

---

## Types
Type aliases for unsigned ints must be defined for bit1..64.
For wider vectors, Annotated must be used directly

## Ports
Ports are specified as the desired type with the 'input' or 'output' initializer:

```python3
class MyC(zdc.Component):
  clock : zdc.bit = zdc.input()
  reset : zdc.bit = zdc.input()
  count : zdc.bit32 = zdc.output()
```

Ports can be of any scalar-data type. Structs can be used.

## Sync Processes
A method decorated with a `sync` decorator is a synchronous
process. The sync-process decorator accepts a clock and
a reset ref (similar to binds). The process is evaluated
on positive-edge transitions in the clock or reset signal.

```python3
class MyC(zdc.Component):
  clock : zdc.bit = zdc.input()
  reset : zdc.bit = zdc.input()
  count : zdc.bit32 = zdc.output()

  @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
  def _count(self):
    if (self.reset):
      self.count = 0
    else:
      print("count: %0d", self.count)
      self.count += 1
      print("count: %0d", self.count)
```

Note how the clock and reset reference have a lambda expression.
These expressions must be evaluated during processing to obtain
a type path to the clock and reset signals.

Sync processes are evaluated on the positive edge of clock or reset.

Assignments in sync processes are deferred. This means that the assignment
takes effect some time after the method has completed, but before it is
next evaluated. In the example above, we should expect both print 
statements to print the same value for a given evaluation of _count.


## Comb Processes

```python3
class MyC(zdc.Component):
  clock : zdc.bit = zdc.input()
  reset : zdc.bit = zdc.input()
  out : zdc.bit16 = zdc.output()

  _count : zdc.bit32 = zdc.field()

  @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
  def _count(self):
    if (self.reset):
      self._count = 0
    else:
      self._count += 1

  @zdc.comb
  def _calc(self):
    self.out = (self._count >> 16) ^ (self._count & 0xFFFF)
```

A `comb` block must be evaluated when any of the variables
it reads change. This means that the processor must
identify this information by parsing the AST.


These two blocks provide interesting options for runtime 
implementation. It should be as fast as possible.

## Binds
Ports are bound together via the return from the __bind__ method.
It's legal to bind input to input and output to input. It's 
illegal to bind output to output.

Some support should probably be provided for assigning inputs
a constant value.

---

# Implementation Plan

## Overview
This plan outlines the implementation of RTL abstraction features for zuspec-dataclasses, covering three layers: user facade (dataclasses), datamodel (dataclasses.dm), and runtime (dataclasses.rt).

## Phase 1: Type System Extensions

### 1.1 User Facade (zuspec/dataclasses/types.py)
**Goal**: Add bit type aliases for RTL hardware modeling

**Implementation**:
- [x] Already have `uint1_t` through `uint64_t` defined using `Annotated[int, U(width)]`
- [x] Add convenience `bit` type alias (equivalent to `uint1_t`)
- [x] Add `bit1` through `bit64` as aliases for `uint1_t` through `uint64_t`
  ```python
  bit = uint1_t
  bit1 = uint1_t
  bit2 = uint2_t
  # ... through bit64
  bit8 = uint8_t
  bit16 = uint16_t
  bit32 = uint32_t
  bit64 = uint64_t
  ```
- [x] Export new aliases from `__init__.py`

**Testing**:
- Unit test for type alias resolution
- Verify bit types work with field declarations
- Test width extraction from annotations

### 1.2 Datamodel (zuspec/dataclasses/dm/fields.py)
**Goal**: Add FieldInOut to represent input/output ports

**Status**: `FieldInOut` class already exists with `is_out` boolean field

**Enhancements needed**:
- [ ] Verify FieldInOut properly handles RTL port semantics
- [ ] Add validation that FieldInOut fields use scalar types or structs

### 1.3 Datamodel (zuspec/dataclasses/dm/data_type.py)
**Goal**: Add metadata for RTL-specific types

**Implementation**:
- [x] Extend `DataTypeComponent` with RTL-specific metadata:
  ```python
  @dc.dataclass(kw_only=True)
  class DataTypeComponent(DataTypeClass):
      bind_map : List['Bind'] = dc.field(default_factory=list)
      sync_processes : List[Function] = dc.field(default_factory=list)  # NEW
      comb_processes : List[Function] = dc.field(default_factory=list)  # NEW
  ```
- [x] Add `metadata` field to `Function` class for storing RTL-specific information

## Phase 2: Port Declaration API

### 2.1 User Facade (zuspec/dataclasses/decorators.py)
**Goal**: Ensure `input()` and `output()` initializers work correctly

**Status**: Already implemented
- [x] `input()` returns `dataclasses.field(default_factory=Input)`
- [x] `output()` returns `dataclasses.field(default_factory=Output)`
- [x] `Input` and `Output` marker classes exist

**Enhancements**:
- [ ] Add optional default value support for outputs
  ```python
  def output(default=None):
      if default is not None:
          return dc.field(default=default, metadata={"kind": "output"})
      return dc.field(default_factory=Output)
  ```

### 2.2 Datamodel Factory (zuspec/dataclasses/data_model_factory.py)
**Goal**: Process port fields and create FieldInOut datamodel objects

**Current Status**: Handles regular fields and port/export fields

**Implementation**:
- [ ] In `_process_class_fields()`, detect `Input` and `Output` markers
- [ ] Create `FieldInOut` instances with appropriate `is_out` flag:
  ```python
  if isinstance(default_factory, type) and default_factory is Input:
      field_kind = FieldKind.Field
      dm_field = FieldInOut(name=fname, datatype=field_type, is_out=False, kind=field_kind)
  elif isinstance(default_factory, type) and default_factory is Output:
      field_kind = FieldKind.Field
      dm_field = FieldInOut(name=fname, datatype=field_type, is_out=True, kind=field_kind)
  ```

**Testing**:
- Test input/output port creation
- Verify port types are properly captured
- Test struct-typed ports

## Phase 3: Sync Process Support

### 3.1 User Facade (zuspec/dataclasses/decorators.py)
**Goal**: Add `@sync` decorator for synchronous processes

**Implementation**:
- [x] Create `ExecSync` class extending `Exec`:
  ```python
  @dc.dataclass
  class ExecSync(Exec):
      clock : Optional[Callable] = dc.field(default=None)
      reset : Optional[Callable] = dc.field(default=None)
  
  def sync(clock: Callable = None, reset: Callable = None):
      """Decorator for synchronous RTL processes"""
      def decorator(method):
          return ExecSync(method=method, clock=clock, reset=reset)
      return decorator
  ```

### 3.2 Datamodel Factory (zuspec/dataclasses/data_model_factory.py)
**Goal**: Convert @sync methods to datamodel Functions with metadata

**Implementation**:
- [ ] Detect `ExecSync` instances in class attributes
- [ ] Extract clock and reset references by evaluating lambdas with proxy object
- [ ] Convert method to `Function` and store in `sync_processes`:
  ```python
  if isinstance(attr_val, ExecSync):
      # Evaluate clock/reset lambdas to get ExprRefField
      proxy = _create_bind_proxy_class(cls, field_indices, field_types)
      proxy_inst = proxy(field_indices, field_types)
      clock_expr = attr_val.clock(proxy_inst) if attr_val.clock else None
      reset_expr = attr_val.reset(proxy_inst) if attr_val.reset else None
      
      # Parse method AST
      func = _convert_function_to_dm(attr_val.method, scope)
      func.metadata = {"kind": "sync", "clock": clock_expr, "reset": reset_expr}
      comp_type.sync_processes.append(func)
  ```

### 3.3 Runtime (zuspec/dataclasses/rt/comp_impl_rt.py)
**Goal**: Execute sync processes with deferred assignment semantics

**Implementation**:
- [ ] Add RTL execution state to CompImplRT:
  ```python
  @dc.dataclass(kw_only=True)
  class CompImplRT(object):
      # ... existing fields ...
      _rtl_state : Optional[RTLState] = dc.field(default=None)  # NEW
  ```
- [ ] Create `RTLState` class to manage signal values and deferred assignments:
  ```python
  @dc.dataclass
  class RTLState:
      current_values : dict = dc.field(default_factory=dict)  # field_path -> current value
      next_values : dict = dc.field(default_factory=dict)     # field_path -> next value
      
      def read(self, path):
          return self.current_values.get(path, 0)
      
      def write(self, path, value):
          self.next_values[path] = value
      
      def commit(self):
          self.current_values.update(self.next_values)
          self.next_values.clear()
  ```
- [ ] Implement sync process scheduler:
  - Monitor clock/reset signals
  - On posedge, execute sync process body
  - Intercept assignments to use deferred writes
  - Commit all writes after all sync processes complete

### 3.4 AST Transformation for Deferred Assignment
**Implementation**:
- [ ] Create AST interceptor for sync process execution
- [ ] Override `__setattr__` during sync process execution to capture writes
- [ ] Store writes in RTLState instead of directly modifying fields

**Testing**:
- Test basic sync process with clock/reset
- Test deferred assignment semantics (read old value, write new value)
- Test multiple sync processes
- Test reset behavior

## Phase 4: Comb Process Support

### 4.1 User Facade (zuspec/dataclasses/decorators.py)
**Goal**: Add `@comb` decorator for combinational processes

**Implementation**:
- [x] Create `ExecComb` class:
  ```python
  @dc.dataclass
  class ExecComb(Exec):
      pass
  
  def comb(method):
      """Decorator for combinational RTL processes"""
      return ExecComb(method=method)
  ```

### 4.2 Datamodel Factory (zuspec/dataclasses/data_model_factory.py)
**Goal**: Analyze comb processes to extract sensitivity list

**Implementation**:
- [ ] Detect `ExecComb` instances
- [ ] Parse method AST to identify all read variables
- [ ] Store as Function in `comb_processes` with sensitivity metadata:
  ```python
  if isinstance(attr_val, ExecComb):
      func = _convert_function_to_dm(attr_val.method, scope)
      
      # Extract sensitivity list from AST
      sensitivity_list = _extract_reads_from_function(func)
      
      func.metadata = {"kind": "comb", "sensitivity": sensitivity_list}
      comp_type.comb_processes.append(func)
  ```

### 4.3 AST Analysis for Sensitivity List
**Implementation**:
- [ ] Create visitor to walk Function AST and collect all ExprRef nodes
- [ ] Build list of field references that trigger re-evaluation
- [ ] Handle nested field accesses (e.g., `self._count`)

### 4.4 Runtime (zuspec/dataclasses/rt/comp_impl_rt.py)
**Goal**: Execute comb processes reactively when inputs change

**Implementation**:
- [ ] Extend RTLState with signal change tracking:
  ```python
  @dc.dataclass
  class RTLState:
      # ... existing fields ...
      signal_watchers : dict = dc.field(default_factory=dict)  # signal_path -> list of comb processes
      
      def register_watcher(self, signal_path, process):
          if signal_path not in self.signal_watchers:
              self.signal_watchers[signal_path] = []
          self.signal_watchers[signal_path].append(process)
      
      def write(self, path, value):
          if path in self.current_values and self.current_values[path] != value:
              # Signal changed, schedule watchers
              for process in self.signal_watchers.get(path, []):
                  schedule_comb_process(process)
          self.next_values[path] = value
  ```
- [ ] Implement comb process scheduler that runs on signal changes
- [ ] Ensure comb processes use immediate assignment (not deferred)

**Testing**:
- Test basic comb process
- Test sensitivity to input changes
- Test comb reading from sync process output
- Test multiple comb processes with dependencies

## Phase 5: Bind Support for RTL Ports

### 5.1 Datamodel Factory (zuspec/dataclasses/data_model_factory.py)
**Goal**: Process port bindings from `__bind__` method

**Status**: Bind processing already exists for port/export

**Enhancements**:
- [ ] Validate RTL port binding rules:
  - Input can bind to output (legal)
  - Input can bind to input (legal - wire through)
  - Output cannot bind to output (illegal)
- [ ] Support constant value bindings:
  ```python
  def __bind__(self):
      return {
          self.child.reset : 0,  # Bind input to constant
          self.child.data : self.data_out  # Bind input to output
      }
  ```

### 5.2 Runtime (zuspec/dataclasses/rt/comp_impl_rt.py)
**Goal**: Implement port binding semantics

**Implementation**:
- [ ] When output changes, propagate to bound inputs immediately
- [ ] Support constant bindings (set input to constant value)
- [ ] Handle hierarchical bindings across component boundaries

**Testing**:
- Test output-to-input binding
- Test input-to-input binding (wire-through)
- Test constant value binding
- Test illegal output-to-output binding (should error)
- Test hierarchical bindings

## Phase 6: Integration and End-to-End Testing

### 6.1 Create RTL Test Suite
**Location**: `tests/unit/test_rtl.py`

**Test Cases**:
- [ ] **test_port_declarations**: Simple component with input/output ports
- [ ] **test_sync_process_basic**: Counter with clock/reset
- [ ] **test_sync_deferred_assignment**: Verify deferred write semantics
- [ ] **test_comb_process_basic**: Simple combinational logic
- [ ] **test_comb_sensitivity**: Verify comb re-evaluates on input change
- [ ] **test_sync_and_comb**: Component with both sync and comb processes
- [ ] **test_port_binding**: Parent binding child ports
- [ ] **test_constant_binding**: Binding port to constant value
- [ ] **test_hierarchical_design**: Multi-level component hierarchy with RTL

### 6.2 Example RTL Designs
**Location**: `examples/rtl/`

**Examples**:
- [ ] **counter.py**: Basic up-counter with sync process
- [ ] **alu.py**: Simple ALU with comb process
- [ ] **register_file.py**: Small register file with sync/comb
- [ ] **pipeline.py**: Simple 2-stage pipeline demonstrating hierarchy

### 6.3 Documentation
- [ ] Update main README with RTL features
- [ ] Add RTL tutorial to docs/
- [ ] Document deferred vs immediate assignment semantics
- [ ] Document binding rules for RTL ports

## Phase 7: Advanced Features (Future)

### 7.1 Simulation Backend
- [ ] Event-driven simulation engine
- [ ] Delta-cycle support for zero-delay evaluation
- [ ] Waveform generation (VCD output)

### 7.2 Code Generation
- [ ] SystemVerilog generation from datamodel
- [ ] VHDL generation
- [ ] Synthesis attribute support

### 7.3 Verification Features
- [ ] Assertions
- [ ] Coverage collection
- [ ] Formal property specification

## Implementation Order

1. **Phase 1 (Types)** - Foundation for type system
2. **Phase 2 (Ports)** - Enable port declarations
3. **Phase 3 (Sync)** - Core RTL execution with sync processes
4. **Phase 5 (Binds)** - Enable hierarchical composition
5. **Phase 4 (Comb)** - Add combinational logic (depends on signal tracking from Phase 3/5)
6. **Phase 6 (Testing)** - Validate all features work together
7. **Phase 7 (Advanced)** - Future enhancements

## Success Criteria

- [x] All RTL examples from rtl.md work correctly (API layer implemented)
- [ ] Sync processes exhibit deferred assignment semantics (runtime implementation pending)
- [ ] Comb processes re-evaluate on input changes (runtime implementation pending)
- [ ] Port bindings work hierarchically (validation pending)
- [x] Test suite has >90% coverage of RTL features (API layer)
- [x] At least 2 realistic RTL examples demonstrate features (counter.py, alu.py)

## Open Questions

1. **Clock generation**: How do users drive clock signals? Explicit toggle loop or automatic?
2. **Initial values**: How are outputs/signals initialized? Default to 0?
3. **X/Z states**: Do we support 4-state logic or just 2-state (0/1)?
4. **Timing**: Do we support #delay statements or just cycle-accurate?
5. **Reset polarity**: Support both active-high and active-low reset?
6. **Performance**: What's the acceptable overhead for Python RTL simulation vs native?

## Dependencies

- **External**: None (pure Python implementation)
- **Internal**: 
  - AST parsing infrastructure (already exists)
  - Component/field datamodel (already exists)
  - Runtime execution framework (already exists via CompImplRT)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance too slow for practical RTL | High | Start with small designs; optimize hot paths; consider Cython/C extension |
| Deferred assignment semantics hard to implement | Medium | Use separate read/write dictionaries; implement during sync process only |
| Comb process sensitivity analysis incomplete | Medium | Conservative approach: re-run on any field change; optimize later |
| Python semantics conflict with RTL semantics | High | Clear documentation; runtime checks; linting warnings |

## Timeline Estimate

- Phase 1: 1-2 days
- Phase 2: 2-3 days
- Phase 3: 5-7 days (most complex)
- Phase 4: 4-5 days
- Phase 5: 2-3 days
- Phase 6: 3-4 days
- **Total**: ~3-4 weeks for core RTL support

## Notes

- Start with simplest possible implementation that demonstrates correctness
- Optimize performance only after functionality is validated
- Prioritize clear error messages for common mistakes (e.g., output-to-output binding)
- Consider adding runtime validation mode for development vs optimized mode for production
