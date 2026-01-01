"""Tracer protocol for method call tracing in runtime components."""
from contextlib import contextmanager
from typing import Protocol, Dict, Any, Optional, TYPE_CHECKING, runtime_checkable
from dataclasses import dataclass

if TYPE_CHECKING:
    from .obj_factory import ObjFactory
    from ..types import Component

@dataclass
class Thread:
    """Represents a thread of execution in the simulation.
    
    Tracks thread ID, parent thread (if nested), and the component that started it.
    """
    tid: int
    parent: Optional['Thread'] = None
    component: Optional['Component'] = None  # Component that started this thread (for @process)
    
    def __repr__(self):
        parent_id = f", parent={self.parent.tid}" if self.parent else ""
        comp_name = f", comp={type(self.component).__name__}" if self.component else ""
        return f"Thread(tid={self.tid}{parent_id}{comp_name})"


class Tracer(Protocol):
    """Protocol for tracing method calls on Component instances.
    
    Implementations can track method entry/exit with timing information.
    """
    
    def enter(self, method: str, thread: Thread, time_ns: float, args: Dict[str, Any]) -> None:
        """Called when entering a traced method.
        
        Args:
            method: Name of the method being called
            thread: Thread object representing the execution context
            time_ns: Current simulation time in nanoseconds
            args: Dictionary of argument names to values
        """
        ...
    
    def leave(self, method: str, thread: Thread, time_ns: float, ret: Any, exc: Optional[Exception]) -> None:
        """Called when leaving a traced method.
        
        Args:
            method: Name of the method being called
            thread: Thread object representing the execution context
            time_ns: Current simulation time in nanoseconds
            ret: Return value from the method (None if exception)
            exc: Exception raised, if any
        """
        ...


@runtime_checkable
class SignalTracer(Protocol):
    """Protocol for tracing signal value changes.
    
    Implementations can record signal transitions for waveform viewing.
    """
    
    def signal_change(
        self, 
        component_path: str,
        signal_name: str, 
        time_ns: float, 
        old_value: Any,
        new_value: Any, 
        width: int
    ) -> None:
        """Called when a signal value changes.
        
        Args:
            component_path: Hierarchical path to the component (e.g., "top.child")
            signal_name: Name of the signal that changed
            time_ns: Current simulation time in nanoseconds
            old_value: Previous value of the signal
            new_value: New value of the signal
            width: Bit width of the signal
        """
        ...
    
    def register_signal(
        self,
        component_path: str,
        signal_name: str,
        width: int,
        is_input: bool
    ) -> None:
        """Called when a signal is discovered during component construction.
        
        Args:
            component_path: Hierarchical path to the component
            signal_name: Name of the signal
            width: Bit width of the signal
            is_input: True if this is an input signal, False for output/field
        """
        ...


@contextmanager
def with_tracer(tracer: Tracer, *, enable_signals: bool = False):
    """Context manager to enable tracing for component construction.
    
    Usage:
        with with_tracer(my_tracer):
            c = MyComponent()
        
        # With signal tracing enabled:
        with with_tracer(my_vcd_tracer, enable_signals=True):
            c = MyComponent()
    
    All components created within this context will have their async methods traced.
    If enable_signals is True and the tracer implements SignalTracer, signal 
    value changes will also be traced.
    
    Args:
        tracer: Tracer instance implementing the Tracer protocol
        enable_signals: If True, enable signal-level tracing (requires tracer
                       to implement SignalTracer protocol)
    """
    from .obj_factory import ObjFactory
    factory = ObjFactory.inst()
    old_tracer = factory.tracer
    old_enable_signals = factory.enable_signal_tracing
    factory.tracer = tracer
    factory.enable_signal_tracing = enable_signals
    try:
        yield
    finally:
        factory.tracer = old_tracer
        factory.enable_signal_tracing = old_enable_signals


