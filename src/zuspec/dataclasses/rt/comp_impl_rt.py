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
    _processes : List[Tuple[str, ExecProc]] = dc.field(default_factory=list)
    _tasks : List[asyncio.Task] = dc.field(default_factory=list)
    _processes_started : bool = dc.field(default=False)
    
    # Evaluation state
    _eval_mode : EvalMode = dc.field(default=EvalMode.IDLE)
    _signal_values : Dict[str, Any] = dc.field(default_factory=dict)
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
        """Extract signal name from expression."""
        from ..dm.expr import ExprRefField
        
        if isinstance(expr, ExprRefField):
            fields = [f for f in dc.fields(comp) if not f.name.startswith('_')]
            if expr.index < len(fields):
                return fields[expr.index].name
        return None
    
    def signal_write(self, comp: Component, name: str, value: Any):
        """Handle signal write with mode-aware semantics.
        
        - IDLE: Direct write + schedule dependent processes on timebase
        - SYNC_EVAL: Deferred write (applied after delta cycle)
        - COMB_EVAL: Immediate write + schedule dependent comb processes
        """
        self._init_eval(comp)
        
        if self._eval_mode == EvalMode.SYNC_EVAL:
            # Deferred write - store for later
            self._deferred_writes[name] = value
            
        elif self._eval_mode == EvalMode.COMB_EVAL:
            # Immediate write
            old_value = self._signal_values.get(name)
            self._signal_values[name] = value
            
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
            
            if old_value != value:
                # Propagate to bound signals FIRST (before scheduling processes)
                if name in self._signal_bindings:
                    for target_comp, target_signal in self._signal_bindings[name]:
                        # Write to bound component's signal
                        # This will recursively trigger that component's processes
                        target_comp._impl.signal_write(target_comp, target_signal, value)
                
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
    
    def signal_read(self, comp: Component, name: str) -> Any:
        """Read signal value."""
        self._init_eval(comp)
        return self._signal_values.get(name, 0)
    
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
        from ..dm.expr import ExprRefField
        
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