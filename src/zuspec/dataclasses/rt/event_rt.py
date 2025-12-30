import asyncio
import dataclasses as dc
import inspect
from typing import Callable, Optional

@dc.dataclass
class EventRT:
    """Runtime implementation of Event with callback support.
    
    Supports the 'at' bind site where a callback can be bound that
    gets invoked when the event is set. Callback MUST be async.
    """
    _event: asyncio.Event = dc.field(default_factory=asyncio.Event)
    _callback: Optional[Callable] = dc.field(default=None)
    
    def set(self):
        """Set the event and invoke the callback if bound."""
        self._event.set()
        if self._callback is not None:
            # Callback must be async - schedule it as a task
            if asyncio.iscoroutinefunction(self._callback):
                asyncio.create_task(self._callback())
            else:
                raise RuntimeError(
                    f"Event callback must be async, not sync. "
                    f"Got sync function: {self._callback.__name__}"
                )
    
    def clear(self):
        """Clear the event."""
        self._event.clear()
    
    def is_set(self) -> bool:
        """Check if the event is set."""
        return self._event.is_set()
    
    async def wait(self):
        """Wait for the event to be set."""
        await self._event.wait()
    
    def bind_callback(self, callback: Callable):
        """Bind a callback to the 'at' bind site.
        
        This method is called by the binding infrastructure when
        a callback is bound to the event's 'at' field.
        
        Args:
            callback: Must be an async callable (coroutine function)
            
        Raises:
            TypeError: If callback is not a coroutine function
        """
        if not asyncio.iscoroutinefunction(callback):
            raise TypeError(
                f"Event callback must be async (coroutine function), not sync. "
                f"Got: {callback.__name__ if hasattr(callback, '__name__') else callback}. "
                f"Use 'async def' to define the callback."
            )
        self._callback = callback
