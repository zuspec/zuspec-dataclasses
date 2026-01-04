from __future__ import annotations
import asyncio
import dataclasses as dc
import inspect
from enum import Enum
from typing import TYPE_CHECKING, Optional, List, Tuple, Dict, Any, Set
from ..types import Component
from ..decorators import ExecProc, ExecSync, ExecComb

if TYPE_CHECKING:
    from .obj_factory import ObjFactory, SignalDescriptor
    from .timebase import Timebase


class EvalMode(Enum):
    """Evaluation mode for processes"""
    IDLE = 0         # Not evaluating processes
    SYNC_EVAL = 1    # Evaluating @sync process (deferred writes)
    COMB_EVAL = 2    # Evaluating @comb process (immediate writes)


@dc.dataclass(kw_only=True)
class CompImplRT(object):
    _factory : ObjFactory = dc.field()
    _name : str = dc.field()
    _parent : Component = dc.field()
    _timebase_inst : Optional[Timebase] = dc.field(default=None)
    _tracer : Optional[Any] = dc.field(default=None)  # Tracer instance for this component
    _enable_signal_tracing : bool = dc.field(default=False)  # Whether to trace signal changes
    _processes : List[Tuple[str, ExecProc]] = dc.field(default_factory=list)
    _tasks : List[asyncio.Task] = dc.field(default_factory=list)
    _processes_started : bool = dc.field(default=False)
    
    # Evaluation state
    _eval_mode : EvalMode = dc.field(default=EvalMode.IDLE)
    _signal_values : Dict[str, Any] = dc.field(default_factory=dict)
    _signal_widths : Dict[str, int] = dc.field(default_factory=dict)  # signal -> width for tracing
    _deferred_writes : Dict[str, Any] = dc.field(default_factory=dict)
    _sensitivity : Dict[str, Set] = dc.field(default_factory=dict)  # signal -> set of comb processes
    _sync_processes : List = dc.field(default_factory=list)
    _comb_processes : List = dc.field(default_factory=list)
    _eval_initialized : bool = dc.field(default=False)
    _pending_eval : Set = dc.field(default_factory=set)  # Comb processes to evaluate in next delta
    _signal_bindings : Dict[str, List] = dc.field(default_factory=dict)  # signal -> list of (comp, signal) bound to it

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def parent(self) -> Component:
        return self._parent

    def handle_setattr(self, comp: Component, name: str, value):
        """Handle attribute setting with evaluation awareness.
        
        This method implements the logic for intercepting writes to output fields
        and routing them through the evaluation system.
        """
        # Check if this is an output field that needs special handling
        if hasattr(self, '_eval_initialized') and self._eval_initialized:
            # Check if this field is an output
            from ..decorators import Output
            
            for field in dc.fields(comp):
                if field.name == name:
                    # Check if this is an output field
                    if field.default_factory is Output:
                        # Route output writes through evaluation system
                        self.signal_write(comp, name, value)
                        # Also update the actual field
                        object.__setattr__(comp, name, value)
                        return
                    break
        
        # Normal assignment for inputs and non-evaluated fields
        object.__setattr__(comp, name, value)

    def timebase(self) -> Timebase:
        """Return the timebase, inheriting from parent if not set."""
        if self._timebase_inst is not None:
            return self._timebase_inst
        if self._parent is not None:
            return self._parent._impl.timebase()
        raise RuntimeError("No timebase available")

    def set_timebase(self, tb: Timebase):
        """Set the timebase for this component."""
        self._timebase_inst = tb

    def add_process(self, name: str, proc: ExecProc):
        """Register a process to be started."""
        self._processes.append((name, proc))
    
    def add_signal_binding(self, source_signal: str, target_comp: Component, target_signal: str):
        """Register a binding from source signal to target component's signal.
        
        When source_signal changes, target_signal on target_comp will also be updated.
        """
        if source_signal not in self._signal_bindings:
            self._signal_bindings[source_signal] = []
        self._signal_bindings[source_signal].append((target_comp, target_signal))
    
    def _init_eval(self, comp: Component):
        """Initialize evaluation structures."""
        if self._eval_initialized:
            return
        
        # Lazy import to avoid circular dependencies
        from ..data_model_factory import DataModelFactory
        
        # Get datamodel - use the first non-Component base class if available (the original user class)
        comp_type = type(comp)
        original_cls = comp_type
        for base in comp_type.__bases__:
            if base.__name__ != 'Component' and hasattr(base, '__module__'):
                original_cls = base
                break
        
        factory = DataModelFactory()
        ctx = factory.build(original_cls)
        datamodel = ctx.type_m.get(original_cls.__qualname__)
        
        if not datamodel:
            return
        
        # Store processes
        self._sync_processes = datamodel.sync_processes
        self._comb_processes = datamodel.comb_processes

        # Field-name mapping (datamodel index -> name)
        self._dm_field_names = [f.name for f in getattr(datamodel, 'fields', [])]
        
        # Build sensitivity map (signal_name -> set of comb process indices)
        for idx, comb_func in enumerate(self._comb_processes):
            sensitivity = comb_func.metadata.get('sensitivity', [])
            for signal_ref in sensitivity:
                signal_name = self._get_signal_name(signal_ref, comp)
                if signal_name:
                    if signal_name not in self._sensitivity:
                        self._sensitivity[signal_name] = set()
                    self._sensitivity[signal_name].add(idx)
        
        # Initialize signal values from component fields
        for field in dc.fields(comp):
            if not field.name.startswith('_'):
                value = getattr(comp, field.name, 0)
                self._signal_values[field.name] = value
        
        # Also initialize signal descriptors (inputs/outputs/signals converted to descriptors)
        # Late import to avoid circular dependency
        from .obj_factory import SignalDescriptor
        for attr_name in dir(type(comp)):
            if not attr_name.startswith('_'):
                attr = getattr(type(comp), attr_name, None)
                if isinstance(attr, SignalDescriptor):
                    # Only initialize if not already set, use descriptor's default value
                    if attr.name not in self._signal_values:
                        self._signal_values[attr.name] = attr.default_value
        
        self._eval_initialized = True
        
        # Run comb processes once to set initial output values
        # This is important so outputs reflect the initial state
        for comb_func in self._comb_processes:
            self._eval_mode = EvalMode.COMB_EVAL
            self._execute_function(comp, comb_func)
            self._eval_mode = EvalMode.IDLE
    
    def _get_signal_name(self, expr, comp):
        """Extract signal name/path from an expression.

        Uses datamodel field ordering to map ExprRefField indices, since the
        runtime dataclass may not contain signal fields as dataclass fields.
        """
        from ..ir.expr import ExprRefField, ExprAttribute, TypeExprRefSelf

        def _fields_for_obj(o):
            try:
                return [f for f in dc.fields(o) if not f.name.startswith('_')]
            except Exception:
                return None

        def _field_name_for_index(o, idx: int):
            if isinstance(o, Component):
                names = getattr(self, '_dm_field_names', None)
                if names is not None and idx < len(names):
                    return names[idx]
            fs = _fields_for_obj(o)
            if fs is not None and idx < len(fs):
                return fs[idx].name
            return None

        def _path_expr(e, o):
            if isinstance(e, TypeExprRefSelf):
                return ""
            if isinstance(e, ExprRefField):
                if isinstance(e.base, TypeExprRefSelf):
                    n = _field_name_for_index(o, e.index)
                    return n
                base_p = _path_expr(e.base, o)
                if base_p is None:
                    return None
                # Try to resolve base object to map nested indices
                base_o = o
                if base_p != "":
                    for part in base_p.split('.'):
                        base_o = getattr(base_o, part)
                n = _field_name_for_index(base_o, e.index)
                if n is None:
                    return None
                return n if base_p == "" else f"{base_p}.{n}"
            if isinstance(e, ExprAttribute):
                base_p = _path_expr(e.value, o)
                if base_p is None:
                    return None
                return e.attr if base_p == "" else f"{base_p}.{e.attr}"
            return None

        return _path_expr(expr, comp)
    
    def signal_write(self, comp: Component, name: str, value: Any, width: int = 32):
        """Handle signal write with mode-aware semantics.
        
        - IDLE: Direct write + schedule dependent processes on timebase
        - SYNC_EVAL: Deferred write (applied after delta cycle)
        - COMB_EVAL: Immediate write + schedule dependent comb processes
        
        Args:
            comp: Component instance
            name: Signal name
            value: New value
            width: Bit width of the signal (for tracing)
        """
        self._init_eval(comp)
        
        # Store width for tracing
        if name not in self._signal_widths:
            self._signal_widths[name] = width
        
        if self._eval_mode == EvalMode.SYNC_EVAL:
            # Deferred write - store for later
            self._deferred_writes[name] = value
            
        elif self._eval_mode == EvalMode.COMB_EVAL:
            # Immediate write
            old_value = self._signal_values.get(name)
            self._signal_values[name] = value
            
            # Notify tracer if enabled and value changed
            if old_value != value:
                self._notify_signal_tracer(comp, name, old_value, value, width)
            
            # Propagate to bound signals (eg parent/child bindings, bundle bindings)
            if old_value != value and name in self._signal_bindings:
                for target_comp, target_signal in self._signal_bindings[name]:
                    target_comp._impl.signal_write(target_comp, target_signal, value, width)

            # Schedule dependent comb processes if value changed
            if old_value != value and name in self._sensitivity:
                for proc_idx in self._sensitivity[name]:
                    if proc_idx not in self._pending_eval:
                        self._pending_eval.add(proc_idx)
            
            # If this is an output signal and value changed, notify parent
            if old_value != value and self._parent is not None:
                tb = self.timebase()
                self._notify_parent_of_output_change(comp, name, tb)
        
        else:  # IDLE - user write from outside process
            old_value = self._signal_values.get(name)
            self._signal_values[name] = value
            
            # Notify tracer if enabled and value changed
            if old_value != value:
                self._notify_signal_tracer(comp, name, old_value, value, width)
            
            if old_value != value:
                # Propagate to bound signals FIRST (before scheduling processes)
                if name in self._signal_bindings:
                    for target_comp, target_signal in self._signal_bindings[name]:
                        # Write to bound component's signal
                        # This will recursively trigger that component's processes
                        target_comp._impl.signal_write(target_comp, target_signal, value, width)
                
                # Schedule dependent processes on timebase at delta (0) time
                tb = self.timebase()
                events_scheduled = False
                
                # Check for clock edge (0->1 transition)
                if old_value == 0 and value == 1:
                    # Schedule sync processes for this clock
                    for sync_func in self._sync_processes:
                        clock_expr = sync_func.metadata.get('clock')
                        if clock_expr:
                            sig_name = self._get_signal_name(clock_expr, comp)
                            if sig_name == name:
                                # Schedule sync process evaluation at delta time
                                self._schedule_sync_eval(comp, sync_func, tb)
                                events_scheduled = True
                
                # Schedule dependent comb processes
                if name in self._sensitivity:
                    for proc_idx in self._sensitivity[name]:
                        if proc_idx not in self._pending_eval:
                            self._pending_eval.add(proc_idx)
                            # Schedule comb evaluation at delta time
                            # The timebase can schedule even when not running
                            self._schedule_comb_eval(comp, proc_idx, tb)
                            events_scheduled = True
                
                # If we scheduled events and timebase is not running, advance it
                # This allows synchronous evaluation of comb processes
                if events_scheduled and not tb._running:
                    tb.advance()
    
    def _get_component_path(self, comp: Component) -> str:
        """Get the hierarchical path to this component."""
        parts = []
        c = comp
        while c is not None:
            impl = c._impl
            if impl._name:
                parts.append(impl._name)
            else:
                parts.append(type(c).__name__)
            c = impl._parent
        parts.reverse()
        return ".".join(parts) if parts else type(comp).__name__
    
    def _notify_signal_tracer(self, comp: Component, name: str, old_value: Any, new_value: Any, width: int):
        """Notify the signal tracer of a value change if signal tracing is enabled."""
        if not self._enable_signal_tracing or self._tracer is None:
            return
        
        from .tracer import SignalTracer
        if isinstance(self._tracer, SignalTracer):
            # Get current time
            try:
                tb = self.timebase()
                time_ns = tb.time().as_ns()
            except RuntimeError:
                time_ns = 0.0
            
            comp_path = self._get_component_path(comp)
            self._tracer.signal_change(comp_path, name, time_ns, old_value, new_value, width)
    
    def signal_read(self, comp: Component, name: str) -> Any:
        """Read signal value, handling nested component paths."""
        self._init_eval(comp)
        
        # First check if the full path exists directly (e.g., bundle signals like "io.req")
        if name in self._signal_values:
            return self._signal_values[name]
        
        # Handle nested paths like "child.count_out" by navigating to child component
        if '.' in name:
            parts = name.split('.', 1)
            child_name = parts[0]
            rest_path = parts[1]
            
            # Get the child component
            child = self._signal_values.get(child_name)
            if child is None:
                child = getattr(comp, child_name, None)
            
            if child is not None and hasattr(child, '_impl'):
                # Recursively read from child component
                return child._impl.signal_read(child, rest_path)
        
        return 0
    
    def _schedule_sync_eval(self, comp: Component, sync_func, timebase):
        """Schedule sync process evaluation on timebase at delta (0) time."""
        def eval_sync():
            # Execute sync process
            self._eval_mode = EvalMode.SYNC_EVAL
            self._execute_function(comp, sync_func)
            self._eval_mode = EvalMode.IDLE
            
            # Apply deferred writes
            for sig_name, val in self._deferred_writes.items():
                old_value = self._signal_values.get(sig_name)
                self._signal_values[sig_name] = val
                
                # Notify tracer if enabled and value changed
                if old_value != val:
                    width = self._signal_widths.get(sig_name, 32)
                    self._notify_signal_tracer(comp, sig_name, old_value, val, width)
                
                # Propagate to bound signals (eg parent/child bindings, bundle bindings)
                if old_value != val and sig_name in self._signal_bindings:
                    width = self._signal_widths.get(sig_name, 32)
                    for target_comp, target_signal in self._signal_bindings[sig_name]:
                        target_comp._impl.signal_write(target_comp, target_signal, val, width)

                # Schedule dependent comb processes if value changed
                if old_value != val and sig_name in self._sensitivity:
                    for proc_idx in self._sensitivity[sig_name]:
                        if proc_idx not in self._pending_eval:
                            self._pending_eval.add(proc_idx)
                            self._schedule_comb_eval(comp, proc_idx, timebase)
                
                # If this is an output signal and value changed, notify parent
                # so parent comb processes that read this output can run
                if old_value != val and self._parent is not None:
                    self._notify_parent_of_output_change(comp, sig_name, timebase)
            
            self._deferred_writes.clear()
        
        # Schedule callback at delta time (None = 0 delay)
        timebase.after(None, eval_sync)
    
    def _schedule_comb_eval(self, comp: Component, proc_idx: int, timebase):
        """Schedule comb process evaluation on timebase at delta (0) time."""
        def eval_comb():
            # Check if still pending (avoid duplicate evals)
            if proc_idx not in self._pending_eval:
                return
            
            self._pending_eval.discard(proc_idx)
            
            if proc_idx < len(self._comb_processes):
                comb_func = self._comb_processes[proc_idx]
                self._eval_mode = EvalMode.COMB_EVAL
                self._execute_function(comp, comb_func)
                self._eval_mode = EvalMode.IDLE
        
        # Schedule callback at delta time (None = 0 delay)
        timebase.after(None, eval_comb)
    
    def _execute_function(self, comp: Component, func):
        """Execute a function (sync or comb)."""
        from .executor import Executor
        
        # Create executor with temporary state wrapper
        executor = Executor(self, comp)
        executor.is_deferred = (self._eval_mode == EvalMode.SYNC_EVAL)
        executor.execute_stmts(func.body)
    
    def _notify_parent_of_output_change(self, comp: Component, signal_name: str, timebase):
        """Notify parent that a child output has changed.
        
        This triggers parent comb processes to re-evaluate since they may read this output.
        For simplicity, we schedule all parent comb processes when any child output changes.
        A more sophisticated approach would track which parent processes actually read this signal.
        """
        if self._parent is None or not hasattr(self._parent, '_impl'):
            return
        
        parent_impl = self._parent._impl
        
        # Schedule all parent comb processes since any of them might read this child output
        # This is conservative but correct - parent processes will check if values actually changed
        for proc_idx in range(len(parent_impl._comb_processes)):
            if proc_idx not in parent_impl._pending_eval:
                parent_impl._pending_eval.add(proc_idx)
                parent_impl._schedule_comb_eval(self._parent, proc_idx, timebase)
    
    def _initialize_eval_state(self, comp: Component):
        """Initialize evaluation state for this component if it has sync/comb processes."""
        if self._eval_initialized:
            return
        
        # Lazy import to avoid circular dependencies
        from .eval_state import EvalState
        from .executor import SyncProcessExecutor, CombProcessExecutor
        from ..data_model_factory import DataModelFactory
        
        # Create evaluation state
        self._eval_state = EvalState()
        
        # Get datamodel for this component
        factory = DataModelFactory()
        ctx = factory.build(type(comp))
        datamodel = ctx.type_m.get(type(comp).__qualname__)
        
        if datamodel is None:
            return
        
        # Initialize all fields to 0
        for field in dc.fields(comp):
            if not field.name.startswith('_'):
                self._eval_state.set_value(field.name, 0)
                
        # Create executors
        self._sync_executor = SyncProcessExecutor(self._eval_state, comp)
        self._comb_executor = CombProcessExecutor(self._eval_state, comp)
        
        # Setup comb process watchers
        for comb_func in datamodel.comb_processes:
            sensitivity = comb_func.metadata.get('sensitivity', [])
            
            def make_watcher(func):
                def watcher():
                    self._comb_executor.execute_stmts(func.body)
                return watcher
            
            for signal_ref in sensitivity:
                field_path = self._get_field_path_from_expr(signal_ref, comp)
                self._eval_state.register_watcher(field_path, make_watcher(comb_func))
        
        # Store datamodel for later use
        self._datamodel = datamodel
        self._eval_initialized = True
    
    def _get_field_path_from_expr(self, expr, comp):
        """Extract field path from expression."""
        from ..ir.expr import ExprRefField
        
        if isinstance(expr, ExprRefField):
            fields = [f for f in dc.fields(comp) if not f.name.startswith('_')]
            if expr.index < len(fields):
                return fields[expr.index].name
        
        return None
    
    def set_input(self, comp: Component, field_name: str, value: Any):
        """Set an input signal value."""
        self._initialize_eval_state(comp)
        if hasattr(self, '_eval_state'):
            self._eval_state.write_immediate(field_name, value)
            # Also set the actual field
            setattr(comp, field_name, value)
    
    def get_output(self, comp: Component, field_name: str) -> Any:
        """Get an output signal value."""
        self._initialize_eval_state(comp)
        if hasattr(self, '_eval_state'):
            return self._eval_state.read(field_name)
        return getattr(comp, field_name, 0)
    
    def clock_edge(self, comp: Component, clock_field: str = "clock"):
        """Process a clock edge for simulation."""
        self._initialize_eval_state(comp)
        if not hasattr(self, '_eval_state') or not hasattr(self, '_datamodel'):
            return
        
        # Execute all sync processes for this clock
        for sync_func in self._datamodel.sync_processes:
            clock_expr = sync_func.metadata.get('clock')
            if clock_expr is not None:
                clock_path = self._get_field_path_from_expr(clock_expr, comp)
                if clock_path == clock_field:
                    self._sync_executor.execute_stmts(sync_func.body)
        
        # Commit deferred writes
        self._eval_state.commit()
        
        # Update component fields from evaluation state
        for field in dc.fields(comp):
            if not field.name.startswith('_'):
                value = self._eval_state.read(field.name)
                object.__setattr__(comp, field.name, value)
    
    def eval_comb(self, comp: Component):
        """Evaluate all combinational processes."""
        self._initialize_eval_state(comp)
        if not hasattr(self, '_eval_state') or not hasattr(self, '_datamodel'):
            return
        
        for comb_func in self._datamodel.comb_processes:
            self._comb_executor.execute_stmts(comb_func.body)

    def start_processes(self, comp: Component):
        """Start all registered processes for this component."""
        for name, proc in self._processes:
            task = asyncio.create_task(proc.method(comp))
            self._tasks.append(task)

    def start_all_processes(self, comp: Component):
        """Recursively start all processes in the component tree."""
        if self._processes_started:
            return
        self._processes_started = True
        
        # Start processes for child components first
        for f in dc.fields(comp):
            fo = getattr(comp, f.name)
            if isinstance(fo, Component):
                fo._impl.start_all_processes(fo)
        
        # Start processes for this component
        self.start_processes(comp)

    def post_init(self, comp):
        from .obj_factory import ObjFactory
        print("--> CompImpl.post_init")

        for f in dc.fields(comp):
            fo = getattr(comp, f.name)

            if inspect.isclass(f.type) and issubclass(f.type, Component): # and not f.init:
                print("Comp Field: %s" % f.name)
                if hasattr(fo, "_impl"):
                    fo._impl.post_init(fo)
                    print("Has impl")
                pass
        print("<-- CompImpl.post_init")

#        self.name = self.factory.name_s[-1]


    def build(self, factory):
        pass

    def shutdown(self):
        """Cancel all running process tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks.clear()

    async def wait(self, comp: Component, amt = None):
        """
        Uses the default timebase to suspend execution of the
        calling coroutine for the specified time.
        
        When called and simulation is not already running, this also 
        drives the simulation forward.
        """
        from ..types import Time
        tb = self.timebase()
        
        if not tb._running:
            # Simulation not running: find root and drive simulation
            root = comp
            while root._impl.parent is not None:
                root = root._impl.parent
            root._impl.start_all_processes(root)
            await tb.run_until(amt)
        else:
            # Inside simulation: just wait for the specified time
            await tb.wait(amt)

    def time(self):
        """Returns the current time"""
        from ..types import Time
        tb = self.timebase()
        return tb.time()

    pass