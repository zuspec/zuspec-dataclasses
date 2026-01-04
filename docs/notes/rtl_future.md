# RTL Implementation Future Plan

This document outlines the remaining implementation work for RTL modeling features in zuspec-dataclasses. It builds upon the completed Phase 1 work (type aliases, decorators, and datamodel extensions).

## Current Status (as of 2025-12-17)

**✅ Completed:**
- Phase 1: Type system (bit aliases)
- Phase 2: Port declarations (pre-existing)
- Phase 3.1: @sync decorator API
- Phase 4.1: @comb decorator API
- Datamodel extensions (sync_processes, comb_processes, Function.metadata)
- Test suite for API layer
- Example designs (counter, ALU)

**⏳ Remaining:**
- Datamodel factory processing
- Runtime execution engine
- Port binding validation
- Advanced features (simulation, code generation)

---

## Phase 3: Sync Process Implementation (Continued)

### 3.2 Datamodel Factory Processing
**Goal**: Detect and convert @sync decorated methods to datamodel Functions

**Location**: `src/zuspec/dataclasses/data_model_factory.py`

**Implementation Steps**:

1. **Detect ExecSync instances in _process_component()**
   ```python
   def _process_component(self, t: Type) -> dm.DataTypeComponent:
       # ... existing code ...
       
       # After processing fields, process sync/comb methods
       for name, attr_val in t.__dict__.items():
           if isinstance(attr_val, ExecSync):
               func = self._process_sync_method(t, name, attr_val, field_indices)
               comp_type.sync_processes.append(func)
           elif isinstance(attr_val, ExecComb):
               func = self._process_comb_method(t, name, attr_val, field_indices)
               comp_type.comb_processes.append(func)
   ```

2. **Implement _process_sync_method()**
   ```python
   def _process_sync_method(self, cls: Type, name: str, 
                           exec_sync: ExecSync, 
                           field_indices: Dict[str, int]) -> dm.Function:
       """Convert a @sync decorated method to a datamodel Function."""
       
       # Create proxy instance to evaluate clock/reset lambdas
       proxy = self._create_bind_proxy_class(cls, field_indices, field_types)
       proxy_inst = proxy(field_indices, field_types)
       
       # Evaluate lambdas to get ExprRefField for clock and reset
       clock_expr = None
       reset_expr = None
       if exec_sync.clock is not None:
           clock_expr = exec_sync.clock(proxy_inst)
       if exec_sync.reset is not None:
           reset_expr = exec_sync.reset(proxy_inst)
       
       # Extract method body as AST
       scope = ConversionScope(
           component=None,
           field_indices=field_indices,
           method_params=set(),
           local_vars=set()
       )
       body = self._extract_method_body(cls, exec_sync.method.__name__, scope)
       
       # Create Function with metadata
       func = dm.Function(
           name=name,
           body=body,
           metadata={
               "kind": "sync",
               "clock": clock_expr,
               "reset": reset_expr,
               "method": exec_sync.method
           }
       )
       
       return func
   ```

3. **Handle edge cases**:
   - Methods with no clock or reset specified
   - Invalid lambda expressions
   - Missing clock/reset signals in component
   - Validation that clock/reset point to valid fields

**Testing**:
- Test sync method detection and conversion
- Test clock/reset lambda evaluation
- Test AST extraction of sync method body
- Test metadata preservation
- Test error cases (invalid lambdas, missing signals)

**Estimated Effort**: 2-3 days

---

## Phase 4: Comb Process Implementation (Continued)

### 4.2 Datamodel Factory Processing
**Goal**: Convert @comb methods and extract sensitivity list

**Location**: `src/zuspec/dataclasses/data_model_factory.py`

**Implementation Steps**:

1. **Implement _process_comb_method()**
   ```python
   def _process_comb_method(self, cls: Type, name: str,
                           exec_comb: ExecComb,
                           field_indices: Dict[str, int]) -> dm.Function:
       """Convert a @comb decorated method to a datamodel Function."""
       
       # Extract method body
       scope = ConversionScope(
           component=None,
           field_indices=field_indices,
           method_params=set(),
           local_vars=set()
       )
       body = self._extract_method_body(cls, exec_comb.method.__name__, scope)
       
       # Analyze AST to extract sensitivity list
       sensitivity_list = self._extract_sensitivity_list(body)
       
       # Create Function with metadata
       func = dm.Function(
           name=name,
           body=body,
           metadata={
               "kind": "comb",
               "sensitivity": sensitivity_list,
               "method": exec_comb.method
           }
       )
       
       return func
   ```

2. **Implement _extract_sensitivity_list()**
   ```python
   def _extract_sensitivity_list(self, body: List[dm.Stmt]) -> List[dm.ExprRef]:
       """Walk AST and collect all field references that are read."""
       
       class SensitivityVisitor:
           def __init__(self):
               self.reads = set()
               self.writes = set()
           
           def visit_expr_ref_field(self, expr: dm.ExprRefField):
               # Track reads (but exclude writes in assignments)
               self.reads.add(expr)
           
           def visit_stmt_assign(self, stmt: dm.StmtAssign):
               # Track write target
               if isinstance(stmt.target, dm.ExprRefField):
                   self.writes.add(stmt.target)
               # Visit RHS for reads
               self.visit_expr(stmt.value)
       
       visitor = SensitivityVisitor()
       for stmt in body:
           visitor.visit_stmt(stmt)
       
       # Sensitivity list = reads minus writes
       sensitivity = list(visitor.reads - visitor.writes)
       return sensitivity
   ```

3. **Optimization considerations**:
   - Cache sensitivity analysis results
   - Handle complex expressions (subscripts, attributes)
   - Deal with conditional reads (if/else)
   - Conservative approach: include all possible reads

**Testing**:
- Test comb method detection
- Test sensitivity list extraction
- Test with simple expressions (a + b)
- Test with complex expressions (conditionals, loops)
- Test with nested field accesses

**Estimated Effort**: 2-3 days

---

## Phase 3.3 & 4.4: Runtime Execution Engine

### Overview
Implement runtime support for executing sync and comb processes with proper semantics.

**Location**: `src/zuspec/dataclasses/rt/comp_impl_rt.py` (new file if needed)

### 3.3 Sync Process Runtime

**Goal**: Execute sync processes with deferred assignment semantics

**Architecture**:
```
RTL Simulation Engine
├── Signal Manager (tracks all signal values)
├── Event Queue (time-ordered events)
├── Process Scheduler (sync/comb execution)
└── Assignment Manager (deferred vs immediate)
```

**Implementation Steps**:

1. **Create RTLState class**
   ```python
   @dc.dataclass
   class RTLState:
       """Manages signal values and deferred assignments for RTL simulation."""
       
       # Current values (what reads see)
       current_values: Dict[str, Any] = dc.field(default_factory=dict)
       
       # Next values (pending writes from sync processes)
       next_values: Dict[str, Any] = dc.field(default_factory=dict)
       
       # Signal change callbacks (for comb process triggering)
       watchers: Dict[str, List[Callable]] = dc.field(default_factory=dict)
       
       def read(self, field_path: str) -> Any:
           """Read current value of a signal."""
           return self.current_values.get(field_path, 0)
       
       def write_deferred(self, field_path: str, value: Any):
           """Schedule a deferred write (sync process)."""
           self.next_values[field_path] = value
       
       def write_immediate(self, field_path: str, value: Any):
           """Perform an immediate write (comb process)."""
           old_value = self.current_values.get(field_path)
           self.current_values[field_path] = value
           
           # Trigger watchers if value changed
           if old_value != value:
               for watcher in self.watchers.get(field_path, []):
                   watcher()
       
       def commit(self):
           """Commit all deferred writes to current values."""
           for field_path, value in self.next_values.items():
               old_value = self.current_values.get(field_path)
               self.current_values[field_path] = value
               
               # Trigger watchers if value changed
               if old_value != value:
                   for watcher in self.watchers.get(field_path, []):
                       watcher()
           
           self.next_values.clear()
       
       def register_watcher(self, field_path: str, callback: Callable):
           """Register a callback to be invoked when field changes."""
           if field_path not in self.watchers:
               self.watchers[field_path] = []
           self.watchers[field_path].append(callback)
   ```

2. **Extend CompImplRT with RTL support**
   ```python
   @dc.dataclass(kw_only=True)
   class CompImplRT(object):
       # ... existing fields ...
       
       # RTL simulation state
       _rtl_state: Optional[RTLState] = dc.field(default=None)
       
       def _init_rtl(self, comp_type: dm.DataTypeComponent):
           """Initialize RTL simulation state."""
           if comp_type.sync_processes or comp_type.comb_processes:
               self._rtl_state = RTLState()
               
               # Initialize all field values
               for field in comp_type.fields:
                   field_path = field.name
                   # Initialize to 0 or default value
                   self._rtl_state.current_values[field_path] = 0
               
               # Register comb processes as watchers
               for comb_func in comp_type.comb_processes:
                   sensitivity = comb_func.metadata.get("sensitivity", [])
                   for signal_ref in sensitivity:
                       signal_path = self._get_field_path(signal_ref)
                       self._rtl_state.register_watcher(
                           signal_path,
                           lambda: self._run_comb_process(comb_func)
                       )
   ```

3. **Implement sync process execution**
   ```python
   class SyncProcessExecutor:
       """Executes sync processes with deferred assignment semantics."""
       
       def __init__(self, rtl_state: RTLState):
           self.rtl_state = rtl_state
           self.in_sync_process = False
       
       def execute_sync_process(self, comp: Component, func: dm.Function):
           """Execute a sync process on clock/reset edge."""
           
           # Mark that we're in a sync process (for assignment interception)
           self.in_sync_process = True
           
           try:
               # Execute the function body
               # Assignments will be intercepted to use write_deferred
               self._execute_function(comp, func)
           finally:
               self.in_sync_process = False
       
       def _execute_function(self, comp: Component, func: dm.Function):
           """Execute function body statements."""
           for stmt in func.body:
               self._execute_stmt(comp, stmt)
       
       def _execute_stmt(self, comp: Component, stmt: dm.Stmt):
           """Execute a single statement."""
           if isinstance(stmt, dm.StmtAssign):
               self._execute_assign(comp, stmt)
           elif isinstance(stmt, dm.StmtIf):
               self._execute_if(comp, stmt)
           # ... handle other statement types
       
       def _execute_assign(self, comp: Component, stmt: dm.StmtAssign):
           """Execute assignment with deferred semantics."""
           # Evaluate RHS expression
           value = self._evaluate_expr(comp, stmt.value)
           
           # Get target field path
           field_path = self._get_field_path(stmt.target)
           
           # Deferred write
           self.rtl_state.write_deferred(field_path, value)
       
       def _evaluate_expr(self, comp: Component, expr: dm.Expr) -> Any:
           """Evaluate an expression, reading from current values."""
           if isinstance(expr, dm.ExprRefField):
               field_path = self._get_field_path(expr)
               return self.rtl_state.read(field_path)
           elif isinstance(expr, dm.ExprBin):
               left = self._evaluate_expr(comp, expr.left)
               right = self._evaluate_expr(comp, expr.right)
               return self._apply_binop(expr.op, left, right)
           # ... handle other expression types
   ```

4. **Implement clock edge detection and process scheduling**
   ```python
   class RTLSimulator:
       """Main RTL simulation engine."""
       
       def __init__(self, top_component: Component):
           self.top = top_component
           self.rtl_state = top_component._impl._rtl_state
           self.executor = SyncProcessExecutor(self.rtl_state)
       
       def clock_edge(self, clock_signal: str):
           """Simulate a positive clock edge."""
           
           # Find all sync processes triggered by this clock
           sync_procs = self._find_sync_processes_for_clock(clock_signal)
           
           # Execute all sync processes (deferred writes)
           for comp, func in sync_procs:
               self.executor.execute_sync_process(comp, func)
           
           # Commit all deferred writes
           self.rtl_state.commit()
       
       def reset_edge(self, reset_signal: str):
           """Simulate a reset edge."""
           # Similar to clock_edge but for reset
           sync_procs = self._find_sync_processes_for_reset(reset_signal)
           
           for comp, func in sync_procs:
               self.executor.execute_sync_process(comp, func)
           
           self.rtl_state.commit()
   ```

**Testing**:
- Test basic sync process execution
- Test deferred assignment (read old, write new)
- Test clock edge triggering
- Test reset behavior
- Test multiple sync processes
- Test interaction with comb processes

**Estimated Effort**: 5-7 days

### 4.4 Comb Process Runtime

**Goal**: Execute comb processes reactively with immediate assignment

**Implementation Steps**:

1. **Implement comb process executor**
   ```python
   class CombProcessExecutor:
       """Executes combinational processes with immediate assignment."""
       
       def __init__(self, rtl_state: RTLState):
           self.rtl_state = rtl_state
           self.in_comb_process = False
           self.execution_stack = []  # For detecting combinational loops
       
       def execute_comb_process(self, comp: Component, func: dm.Function):
           """Execute a combinational process."""
           
           # Check for combinational loops
           if func in self.execution_stack:
               raise RuntimeError(
                   f"Combinational loop detected involving {func.name}"
               )
           
           self.execution_stack.append(func)
           self.in_comb_process = True
           
           try:
               self._execute_function(comp, func)
           finally:
               self.in_comb_process = False
               self.execution_stack.pop()
       
       def _execute_assign(self, comp: Component, stmt: dm.StmtAssign):
           """Execute assignment with immediate semantics."""
           # Evaluate RHS
           value = self._evaluate_expr(comp, stmt.value)
           
           # Get target field path
           field_path = self._get_field_path(stmt.target)
           
           # Immediate write (triggers watchers)
           self.rtl_state.write_immediate(field_path, value)
   ```

2. **Implement delta-cycle scheduling**
   ```python
   class DeltaCycleScheduler:
       """Schedules comb process evaluation in delta cycles."""
       
       def __init__(self, rtl_state: RTLState):
           self.rtl_state = rtl_state
           self.pending_comb = set()
           self.executor = CombProcessExecutor(rtl_state)
       
       def schedule_comb(self, comp: Component, func: dm.Function):
           """Schedule a comb process for evaluation."""
           self.pending_comb.add((comp, func))
       
       def run_delta_cycle(self):
           """Execute all pending comb processes until stable."""
           
           max_iterations = 1000  # Prevent infinite loops
           iteration = 0
           
           while self.pending_comb and iteration < max_iterations:
               # Take snapshot of pending processes
               to_execute = list(self.pending_comb)
               self.pending_comb.clear()
               
               # Execute all pending comb processes
               for comp, func in to_execute:
                   self.executor.execute_comb_process(comp, func)
               
               iteration += 1
           
           if iteration >= max_iterations:
               raise RuntimeError(
                   "Delta cycle did not converge after 1000 iterations. "
                   "Possible combinational loop."
               )
   ```

3. **Integrate with signal change notification**
   - When a signal changes (from sync commit or comb write), trigger registered watchers
   - Watchers schedule comb processes in the delta cycle scheduler
   - Run delta cycles until no more changes occur

**Testing**:
- Test basic comb process execution
- Test immediate assignment semantics
- Test sensitivity to input changes
- Test cascaded comb processes (A changes -> B executes -> C changes -> D executes)
- Test combinational loop detection
- Test delta cycle convergence

**Estimated Effort**: 4-5 days

---

## Phase 5: Port Binding Validation

### 5.1 Validate RTL Port Binding Rules

**Goal**: Enforce legal port connections and support constant bindings

**Location**: `src/zuspec/dataclasses/data_model_factory.py`

**Binding Rules**:
- ✅ Legal: output → input (signal flow)
- ✅ Legal: input → input (wire-through/fanout)
- ❌ Illegal: output → output (multiple drivers)
- ✅ Legal: constant → input (tie-off)

**Implementation**:

1. **Extend bind processing in _process_component()**
   ```python
   def _validate_rtl_bind(self, bind: dm.Bind):
       """Validate RTL binding rules."""
       
       lhs_field = self._resolve_field(bind.lhs)
       rhs = bind.rhs
       
       # Check if LHS is an input port
       if not isinstance(lhs_field, dm.FieldInOut) or lhs_field.is_out:
           raise ValueError(
               f"RTL bind: LHS must be an input port, got {lhs_field}"
           )
       
       # Check RHS type
       if isinstance(rhs, dm.ExprConstant):
           # Constant binding - always legal
           return
       
       rhs_field = self._resolve_field(rhs)
       
       if isinstance(rhs_field, dm.FieldInOut):
           if not rhs_field.is_out:
               # Input to input - legal (wire-through)
               return
           else:
               # Output to input - legal (normal connection)
               return
       else:
           raise ValueError(
               f"RTL bind: RHS must be a port or constant, got {rhs_field}"
           )
   ```

2. **Support constant value bindings**
   ```python
   # Example user code:
   def __bind__(self):
       return {
           self.child.reset: 0,        # Tie reset low
           self.child.enable: 1,       # Tie enable high
           self.child.data: self.data  # Normal connection
       }
   ```

3. **Validation error messages**
   - Clear error when output binds to output
   - Suggest alternatives (use intermediate wire)
   - Warning for unbound input ports

**Testing**:
- Test legal bindings (out→in, in→in, const→in)
- Test illegal binding (out→out) raises error
- Test unbound input warning
- Test constant value bindings (0, 1, arbitrary values)
- Test hierarchical bindings

**Estimated Effort**: 2-3 days

---

## Phase 6: Integration and End-to-End Testing

### 6.1 Comprehensive Test Suite

**Location**: `tests/unit/test_rtl_execution.py` (new)

**Test Scenarios**:

1. **Basic sync process**
   ```python
   def test_sync_counter_execution():
       """Test that counter increments on clock edge."""
       counter = Counter()
       sim = RTLSimulator(counter)
       
       # Reset
       counter.reset = 1
       sim.clock_edge("clock")
       assert counter.count == 0
       
       # Release reset and clock
       counter.reset = 0
       sim.clock_edge("clock")
       assert counter.count == 1
       
       sim.clock_edge("clock")
       assert counter.count == 2
   ```

2. **Deferred assignment semantics**
   ```python
   def test_sync_deferred_assignment():
       """Verify reads see old value, writes are deferred."""
       
       @zdc.dataclass
       class DeferredTest(zdc.Component):
           clock : zdc.bit = zdc.input()
           value : zdc.bit8 = zdc.field()
           old_value : zdc.bit8 = zdc.field()
           
           @zdc.sync(clock=lambda s: s.clock)
           def proc(self):
               self.old_value = self.value  # Should read old value
               self.value = self.value + 1  # Increment
       
       dut = DeferredTest()
       sim = RTLSimulator(dut)
       
       dut.value = 5
       sim.clock_edge("clock")
       
       # Both should have seen value=5, now value=6
       assert dut.old_value == 5
       assert dut.value == 6
   ```

3. **Comb process sensitivity**
   ```python
   def test_comb_sensitivity():
       """Test that comb re-evaluates on input change."""
       
       alu = SimpleALU()
       sim = RTLSimulator(alu)
       
       alu.a = 5
       alu.b = 3
       alu.op = 0  # XOR
       sim.eval_comb()
       
       assert alu.result == (5 ^ 3)
       
       # Change input
       alu.a = 7
       # Comb should auto-evaluate
       assert alu.result == (7 ^ 3)
   ```

4. **Sync and comb interaction**
   ```python
   def test_sync_comb_pipeline():
       """Test registered ALU with sync and comb."""
       
       dut = RegisteredALU()
       sim = RTLSimulator(dut)
       
       # Reset
       dut.reset = 1
       sim.clock_edge("clock")
       assert dut.result == 0
       
       # Set inputs
       dut.reset = 0
       dut.a = 10
       dut.b = 5
       dut.op = 1  # ADD
       
       # Comb should compute immediately
       assert dut._alu_out == 15
       
       # Sync captures on clock
       sim.clock_edge("clock")
       assert dut.result == 15
   ```

5. **Hierarchical component with bindings**
   ```python
   def test_hierarchical_rtl():
       """Test parent component with child RTL components."""
       
       @zdc.dataclass
       class Top(zdc.Component):
           clock : zdc.bit = zdc.input()
           reset : zdc.bit = zdc.input()
           result : zdc.bit32 = zdc.output()
           
           counter : Counter = zdc.field()
           
           def __bind__(self):
               return {
                   self.counter.clock: self.clock,
                   self.counter.reset: self.reset,
                   self.result: self.counter.count
               }
       
       top = Top()
       sim = RTLSimulator(top)
       
       top.reset = 1
       sim.clock_edge("clock")
       assert top.result == 0
       
       top.reset = 0
       for i in range(10):
           sim.clock_edge("clock")
       
       assert top.result == 10
   ```

**Estimated Effort**: 3-4 days

---

## Phase 7: Advanced Features (Future)

### 7.1 Waveform Generation

**Goal**: Generate VCD (Value Change Dump) files for waveform viewing

**Implementation**:
- Hook into RTLState to track all signal changes with timestamps
- Write VCD format file with scope hierarchy
- Support for different data types (bit, bit vectors, integers)

**Tools**:
- GTKWave for viewing VCD files
- Python `vcd` library for generation

**Estimated Effort**: 2-3 days

### 7.2 SystemVerilog Code Generation

**Goal**: Generate synthesizable SystemVerilog from datamodel

**Implementation**:
- Walk datamodel Component types
- Generate `module` declarations with ports
- Generate `always_ff` blocks from sync processes
- Generate `always_comb` blocks from comb processes
- Handle bindings as port connections

**Challenges**:
- Python expression semantics vs Verilog
- Type width inference
- Naming conventions
- Non-synthesizable constructs

**Estimated Effort**: 1-2 weeks

### 7.3 Verification Features

**Goal**: Add assertion and coverage support

**Features**:
- Immediate assertions (check conditions during simulation)
- Concurrent assertions (SVA-style temporal properties)
- Code coverage (line, toggle, FSM)
- Functional coverage (covergroups)

**Estimated Effort**: 2-3 weeks

### 7.4 Performance Optimization

**Goal**: Optimize simulation performance

**Techniques**:
- Compiled process execution (bytecode or native)
- Incremental sensitivity analysis
- Event-driven scheduling optimization
- JIT compilation with Numba or Cython
- Parallel process execution where safe

**Estimated Effort**: 2-3 weeks

---

## Implementation Roadmap

### Immediate Next Steps (1-2 weeks)
1. **Phase 3.2**: Datamodel factory for sync processes
2. **Phase 4.2**: Datamodel factory for comb processes
3. **Basic tests**: Verify datamodel generation is correct

### Short Term (3-6 weeks)
4. **Phase 3.3**: Sync process runtime execution
5. **Phase 4.4**: Comb process runtime execution
6. **Phase 5**: Port binding validation
7. **Phase 6**: Comprehensive test suite

### Medium Term (2-3 months)
8. **Phase 7.1**: Waveform generation (VCD)
9. **Basic examples**: Demonstrate end-to-end simulation
10. **Performance baseline**: Measure simulation speed

### Long Term (3-6 months)
11. **Phase 7.2**: SystemVerilog code generation
12. **Phase 7.3**: Verification features
13. **Phase 7.4**: Performance optimization
14. **Production readiness**: Documentation, examples, benchmarks

---

## Success Metrics

### Phase 3-4 (Runtime Execution)
- ✅ All sync processes execute with deferred semantics
- ✅ All comb processes execute with immediate semantics
- ✅ Signal changes trigger comb re-evaluation
- ✅ Delta cycles converge correctly
- ✅ Combinational loops are detected

### Phase 5 (Binding Validation)
- ✅ Illegal bindings (output→output) are caught
- ✅ Legal bindings work correctly
- ✅ Constant bindings work
- ✅ Clear error messages guide users

### Phase 6 (Integration)
- ✅ Test suite has >95% coverage
- ✅ All examples run correctly
- ✅ No regressions in existing tests
- ✅ Performance is acceptable (>10K cycles/sec for small designs)

### Phase 7 (Advanced)
- ✅ VCD files viewable in GTKWave
- ✅ Generated SystemVerilog synthesizes in Vivado/Quartus
- ✅ Assertions catch design bugs
- ✅ Performance >100K cycles/sec for optimized designs

---

## Dependencies

### External Libraries
- **Python standard library**: ast, inspect, dataclasses
- **VCD generation**: `vcd` package (optional, Phase 7.1)
- **Performance**: `numba` or `cython` (optional, Phase 7.4)

### Internal Dependencies
- **AST parsing**: Already implemented in data_model_factory.py
- **Expression evaluation**: Needs implementation
- **Component runtime**: Extend existing CompImplRT

### Development Tools
- **Testing**: pytest (already in use)
- **Waveform viewing**: GTKWave (user-installed)
- **Verilog simulation**: Verilator or ModelSim (for validation)

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance too slow for practical use | High | Profile early, optimize hot paths, consider Cython |
| Deferred assignment hard to implement correctly | Medium | Extensive testing, clear separation of read/write |
| Comb loops cause hangs | Medium | Iteration limits, loop detection, good error messages |
| Python semantics don't match Verilog | High | Clear documentation, runtime warnings, linting |
| Code generation produces invalid Verilog | High | Extensive validation against commercial simulators |
| Limited user adoption due to complexity | Medium | Great documentation, simple examples, tutorials |

---

## Open Questions

1. **Timing model**: Do we support #delays or just cycle-accurate?
   - **Recommendation**: Start with cycle-accurate, add timing later

2. **Four-state logic**: Support X/Z values or just 0/1?
   - **Recommendation**: Start with two-state, add X/Z for Phase 7

3. **Reset polarity**: Support both active-high and active-low?
   - **Recommendation**: User specifies polarity in process logic

4. **Clock domains**: Support multiple clocks?
   - **Recommendation**: Yes, track clock source per sync process

5. **Non-blocking assignments**: Support NBA timing in sync processes?
   - **Recommendation**: All sync assignments are non-blocking (deferred)

6. **Blocking assignments**: Support in comb processes?
   - **Recommendation**: All comb assignments are blocking (immediate)

7. **Initial blocks**: Support initialization before simulation?
   - **Recommendation**: Use Component.__init__ or field defaults

8. **Always blocks**: Combine @sync and @comb or keep separate?
   - **Decision made**: Keep separate for clarity

---

## Documentation Needs

### User Documentation
- RTL modeling guide (tutorial-style)
- API reference for decorators and types
- Examples gallery (counter, ALU, FSM, pipeline)
- Best practices guide
- Performance tuning guide

### Developer Documentation
- Architecture overview
- Datamodel structure
- Runtime execution flow
- Adding new features guide
- Testing strategy

### Migration Guides
- From SystemVerilog to zuspec-dataclasses
- From MyHDL/Migen to zuspec-dataclasses
- Integration with existing Python testbenches

---

## Conclusion

The foundation for RTL modeling has been successfully implemented. The remaining work focuses on:

1. **Datamodel integration** (Phases 3.2, 4.2) - Connect decorators to internal representation
2. **Runtime execution** (Phases 3.3, 4.4) - Make it actually simulate
3. **Validation** (Phase 5) - Ensure correct usage
4. **Testing** (Phase 6) - Verify everything works
5. **Advanced features** (Phase 7) - Make it production-ready

Estimated total effort: **8-12 weeks** for core functionality (Phases 3-6), plus **2-4 months** for advanced features (Phase 7).

The implementation plan is conservative and incremental, with clear milestones and testing at each stage. The architecture is designed to be extensible for future enhancements.
