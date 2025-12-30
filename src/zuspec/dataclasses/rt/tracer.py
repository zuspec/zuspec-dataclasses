"""Tracer protocol for method call tracing in runtime components."""
from contextlib import contextmanager
from typing import Protocol, Dict, Any, Optional, TYPE_CHECKING
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


@contextmanager
def with_tracer(tracer: Tracer):
    """Context manager to enable tracing for component construction.
    
    Usage:
        with with_tracer(my_tracer):
            c = MyComponent()
    
    All components created within this context will have their async methods traced.
    """
    from .obj_factory import ObjFactory
    factory = ObjFactory.inst()
    old_tracer = factory.tracer
    factory.tracer = tracer
    try:
        yield
    finally:
        factory.tracer = old_tracer


