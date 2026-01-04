import asyncio
import dataclasses as dc
import inspect
from typing import Callable, Optional

@dc.dataclass
class EventRT:
    """Runtime implementation of Event with callback support.
    
    Supports the 'at' bind site where a callback can be bound that
    gets invoked when the event is set. Callback can be sync or async.
    """
    _event: asyncio.Event = dc.field(default_factory=asyncio.Event)
    _callback: Optional[Callable] = dc.field(default=None)
    
    def set(self):
        """Set the event and invoke the callback if bound."""
        self._event.set()
        if self._callback is not None:
            # Support both async and sync callbacks
            if asyncio.iscoroutinefunction(self._callback):
                # Async callback - schedule it as a task
                asyncio.create_task(self._callback())
            else:
                # Sync callback - call directly
                self._callback()
    
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
            callback: Can be either sync or async callable. Async callbacks
                     are scheduled as tasks, sync callbacks are called directly.
        """
        self._callback = callback
